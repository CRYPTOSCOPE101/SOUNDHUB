cmake_minimum_required(VERSION 3.22)

project(SoundHub VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- JUCE: prefer a local checkout (JUCE_ROOT), else fetch 8.0.9 ----
if(NOT DEFINED JUCE_ROOT)
    include(FetchContent)
    FetchContent_Declare(
        JUCE
        GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
        GIT_TAG        8.0.9
        GIT_SHALLOW    TRUE
    )
    FetchContent_GetProperties(JUCE)
    if(NOT juce_POPULATED)
        FetchContent_Populate(JUCE)
    endif()
    set(JUCE_ROOT "${juce_SOURCE_DIR}")
endif()

list(APPEND CMAKE_MODULE_PATH "${JUCE_ROOT}/cmake")
include(JUCE)

# The SoundHub VST3 is a UI companion: it does no audio processing and is
# never a synth/MIDI effect. Only the VST3 format is built (Cubase, FL Studio
# and any other VST3 host share the same binary).
juce_add_plugin(SoundHub
    VENDOR_NAME "SoundHub"
    VENDOR_WEBSITE "https://github.com/soundXlab/SoundHub"
    VENDOR_EMAIL "dev@soundhub.local"
    VERSION "0.1.0"
    PLUGIN_MANUFACTURER_CODE SndH
    PLUGIN_CODE SndH
    FORMATS VST3
    PRODUCT_NAME "SoundHub"
    PLUGIN_IS_A_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_NEEDS_KEYBOARD_FOCUS TRUE
    COPY_PLUGIN_AFTER_BUILD FALSE
)

target_sources(SoundHub PRIVATE
    Source/PluginProcessor.cpp
    Source/PluginEditor.cpp
    Source/AgentClient.cpp
)

target_link_libraries(SoundHub PRIVATE
    juce::juce_audio_plugin_client
    juce::juce_audio_utils
    juce::juce_gui_basics
    juce::juce_events
)
