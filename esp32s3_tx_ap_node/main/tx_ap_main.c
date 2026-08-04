#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

/* =========================
 * 런타임 설정(기본값)
 * =========================
 */
#ifndef TX_AP_SSID
#define TX_AP_SSID "MeshSense_TX_AP"
#endif
#ifndef TX_AP_PASS
#define TX_AP_PASS "mstx1234"
#endif
#ifndef TX_AP_CHANNEL
#define TX_AP_CHANNEL 6
#endif
#ifndef TX_AP_MAX_CONN
#define TX_AP_MAX_CONN 4
#endif
#ifndef TX_AP_BEACON_INTERVAL_TU
#define TX_AP_BEACON_INTERVAL_TU 100
#endif
#ifndef TX_AP_ESPNOW_INTERVAL_MS
#define TX_AP_ESPNOW_INTERVAL_MS 10
#endif
static const uint8_t BROADCAST_MAC[ESP_NOW_ETH_ALEN] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

/* 연결된 STA의 MAC을 ESP-NOW peer로 등록 → unicast로 보내 DTIM 게이팅 우회.
 * SoftAP broadcast/multicast 프레임은 DTIM beacon마다 묶여 전송되므로 100Hz CSI 자극 불가.
 * unicast는 즉시 전송. */
#define MAX_STA_PEERS 4
static uint8_t g_sta_peers[MAX_STA_PEERS][ESP_NOW_ETH_ALEN];
static volatile int g_sta_peer_count = 0;

static bool add_sta_peer(const uint8_t *mac)
{
    for (int i = 0; i < g_sta_peer_count; ++i) {
        if (memcmp(g_sta_peers[i], mac, ESP_NOW_ETH_ALEN) == 0) {
            return false;
        }
    }
    if (g_sta_peer_count >= MAX_STA_PEERS) {
        return false;
    }
    esp_now_peer_info_t peer = {0};
    memcpy(peer.peer_addr, mac, ESP_NOW_ETH_ALEN);
    peer.channel = (uint8_t)TX_AP_CHANNEL;
    peer.ifidx = WIFI_IF_AP;
    peer.encrypt = false;
    esp_err_t err = esp_now_add_peer(&peer);
    if (err != ESP_OK && err != ESP_ERR_ESPNOW_EXIST) {
        return false;
    }
    memcpy(g_sta_peers[g_sta_peer_count], mac, ESP_NOW_ETH_ALEN);
    g_sta_peer_count++;
    return true;
}

static void remove_sta_peer(const uint8_t *mac)
{
    for (int i = 0; i < g_sta_peer_count; ++i) {
        if (memcmp(g_sta_peers[i], mac, ESP_NOW_ETH_ALEN) == 0) {
            esp_now_del_peer(mac);
            for (int j = i; j + 1 < g_sta_peer_count; ++j) {
                memcpy(g_sta_peers[j], g_sta_peers[j + 1], ESP_NOW_ETH_ALEN);
            }
            g_sta_peer_count--;
            return;
        }
    }
}

static const char *TAG = "TX_AP_NODE";
static uint32_t g_enow_seq = 0;
static volatile uint32_t g_enow_ok = 0;
static volatile uint32_t g_enow_fail = 0;
static volatile uint32_t g_enow_cb_ok = 0;
static volatile uint32_t g_enow_cb_fail = 0;

static void esp_now_send_cb(const uint8_t *mac, esp_now_send_status_t status)
{
    (void)mac;
    if (status == ESP_NOW_SEND_SUCCESS) {
        g_enow_cb_ok++;
    } else {
        g_enow_cb_fail++;
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    (void)arg;
    (void)event_data;
    if (event_base != WIFI_EVENT) {
        return;
    }

    if (event_id == WIFI_EVENT_AP_STACONNECTED) {
        wifi_event_ap_staconnected_t *event = (wifi_event_ap_staconnected_t *)event_data;
        bool added = add_sta_peer(event->mac);
        ESP_LOGI(TAG, "STA connected: " MACSTR ", aid=%d, peer_added=%d, peers=%d",
                 MAC2STR(event->mac), event->aid, added, g_sta_peer_count);
    } else if (event_id == WIFI_EVENT_AP_STADISCONNECTED) {
        wifi_event_ap_stadisconnected_t *event = (wifi_event_ap_stadisconnected_t *)event_data;
        remove_sta_peer(event->mac);
        ESP_LOGI(TAG, "STA disconnected: " MACSTR ", aid=%d, peers=%d",
                 MAC2STR(event->mac), event->aid, g_sta_peer_count);
    }
}

static void init_esp_now(void)
{
    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_register_send_cb(esp_now_send_cb));

    esp_now_peer_info_t peer = {0};
    memcpy(peer.peer_addr, BROADCAST_MAC, ESP_NOW_ETH_ALEN);
    peer.channel = (uint8_t)TX_AP_CHANNEL;
    peer.ifidx = WIFI_IF_AP;
    peer.encrypt = false;
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));

    /* ESP-NOW rate 강제는 사용하지 않음 (default 사용).
     * - HT20 MCS0 / 11g 6M OFDM 강제 모두 RX CSI 콜백 또는 무선 송신 신뢰성을 악화시킴
     * - default rate가 실측 가장 안정적 (cb 발생률 + tx 성공률 균형) */

    ESP_LOGI(TAG,
             "ESP-NOW broadcaster ready ch=%d interval=%dms (CSI excitation, 100Hz target)",
             TX_AP_CHANNEL,
             TX_AP_ESPNOW_INTERVAL_MS);
}

static void init_softap(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));

    wifi_config_t ap_cfg = {0};
    strncpy((char *)ap_cfg.ap.ssid, TX_AP_SSID, sizeof(ap_cfg.ap.ssid) - 1);
    strncpy((char *)ap_cfg.ap.password, TX_AP_PASS, sizeof(ap_cfg.ap.password) - 1);
    ap_cfg.ap.ssid_len = (uint8_t)strlen(TX_AP_SSID);
    ap_cfg.ap.channel = TX_AP_CHANNEL;
    ap_cfg.ap.max_connection = TX_AP_MAX_CONN;
    ap_cfg.ap.pmf_cfg.required = false;
    /* 기본 100 TU(~102ms). 10 TU는 에어타임 붕괴로 CSI gap 유발 — ESP-NOW로 100Hz 유도 */
    ap_cfg.ap.beacon_interval = (uint16_t)TX_AP_BEACON_INTERVAL_TU;

    if (strlen(TX_AP_PASS) >= 8) {
        ap_cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
    } else {
        ap_cfg.ap.authmode = WIFI_AUTH_OPEN;
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_cfg));
    /* HT20 강제는 start 이전에 (이후에 호출하면 무시되는 경우 관측됨).
     * HT40 secondary channel에서 ESP-NOW broadcast가 RX CSI 콜백을 일부 누락시키는 문제 회피. */
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20));

    ESP_LOGI(TAG,
             "SoftAP started ssid=%s channel=%d max_conn=%d beacon=%dTU auth=%s",
             TX_AP_SSID,
             TX_AP_CHANNEL,
             TX_AP_MAX_CONN,
             (int)ap_cfg.ap.beacon_interval,
             ap_cfg.ap.authmode == WIFI_AUTH_OPEN ? "OPEN" : "WPA2");
}

/* ESP-NOW 브로드캐스트: RX CSI 콜백을 100Hz에 가깝게 유도 (L3 UDP보다 L2에 가까움) */
static void esp_now_tx_task(void *arg)
{
    (void)arg;
    uint32_t fail_streak = 0;

    while (1) {
        uint32_t payload = g_enow_seq++;
        int peers = g_sta_peer_count;
        bool any_ok = false;
        if (peers > 0) {
            /* unicast 송신: DTIM 게이팅 우회 → 즉시 송출 → RX CSI 100Hz 자극 */
            for (int i = 0; i < peers; ++i) {
                esp_err_t err = esp_now_send(g_sta_peers[i], (const uint8_t *)&payload, sizeof(payload));
                if (err == ESP_OK) {
                    any_ok = true;
                }
            }
        } else {
            /* STA 미연결 시 fallback: broadcast (peer 등록 안 되어 있으면 실패) */
            esp_err_t err = esp_now_send(BROADCAST_MAC, (const uint8_t *)&payload, sizeof(payload));
            if (err == ESP_OK) {
                any_ok = true;
            }
        }
        if (!any_ok) {
            g_enow_fail++;
            if (++fail_streak == 1 || (fail_streak % 100) == 0) {
                ESP_LOGW(TAG, "esp_now_send failed (streak=%" PRIu32 ", peers=%d)", fail_streak, peers);
            }
        } else {
            g_enow_ok++;
            fail_streak = 0;
        }

        if ((payload % 500) == 0) {
            ESP_LOGI(TAG,
                     "esp_now seq=%" PRIu32 " api(ok=%" PRIu32 " fail=%" PRIu32 ") tx_done(ok=%" PRIu32 " fail=%" PRIu32 ")",
                     payload, g_enow_ok, g_enow_fail, g_enow_cb_ok, g_enow_cb_fail);
        }

        vTaskDelay(pdMS_TO_TICKS(TX_AP_ESPNOW_INTERVAL_MS));
    }
}

void app_main(void)
{
    ESP_ERROR_CHECK(nvs_flash_init());
    init_softap();
    init_esp_now();
    xTaskCreate(esp_now_tx_task, "esp_now_tx", 4096, NULL, 6, NULL);
}
