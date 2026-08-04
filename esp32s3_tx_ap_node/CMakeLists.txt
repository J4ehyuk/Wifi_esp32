cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

set(TX_AP_SSID "MeshSense_TX_AP" CACHE STRING "SoftAP SSID")
set(TX_AP_PASS "mstx1234" CACHE STRING "SoftAP password")
set(TX_AP_CHANNEL "6" CACHE STRING "SoftAP channel")
set(TX_AP_MAX_CONN "4" CACHE STRING "SoftAP max stations")
set(TX_AP_BEACON_INTERVAL_TU "100" CACHE STRING "SoftAP beacon TU (100=default stable; CSI via ESP-NOW)")
set(TX_AP_ESPNOW_INTERVAL_MS "10" CACHE STRING "ESP-NOW broadcast interval (10ms=100Hz target)")

add_compile_definitions(
    TX_AP_SSID=\"${TX_AP_SSID}\"
    TX_AP_PASS=\"${TX_AP_PASS}\"
    TX_AP_CHANNEL=${TX_AP_CHANNEL}
    TX_AP_MAX_CONN=${TX_AP_MAX_CONN}
    TX_AP_BEACON_INTERVAL_TU=${TX_AP_BEACON_INTERVAL_TU}
    TX_AP_ESPNOW_INTERVAL_MS=${TX_AP_ESPNOW_INTERVAL_MS}
)

project(esp32s3_tx_ap_node)
