# KDE's settings pages (KCMs) inside Sloth Center's own window: a small QML module (org.slothos.kcmhost).
# Built during the image build by files/scripts/kcmhost.sh against the image's own Qt and KDE Frameworks, so it
# always matches them; the source is removed after the build.
cmake_minimum_required(VERSION 3.20)
project(kcmhost LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Quick Qml)
find_package(KF6KCMUtils REQUIRED)
find_package(KF6CoreAddons REQUIRED)
qt_policy(SET QTP0001 NEW)

qt_add_qml_module(kcmhost
    URI org.slothos.kcmhost
    VERSION 1.0
    SHARED
    PLUGIN_TARGET kcmhost
    SOURCES kcmview.h kcmview.cpp kcmcatalog.h kcmcatalog.cpp
    OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/qml/org/slothos/kcmhost)
target_link_libraries(kcmhost PRIVATE Qt6::Quick Qt6::Qml KF6::KCMUtilsQuick KF6::KCMUtilsCore KF6::CoreAddons)
