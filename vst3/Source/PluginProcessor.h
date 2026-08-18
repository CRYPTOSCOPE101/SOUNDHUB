#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

namespace soundhub
{

/** SoundHub VST3 companion — an AudioProcessor skeleton with a UI panel.
 *
 * No audio processing happens here (pass-through processBlock). All SoundHub
 * work — push, review, comments, catalog, asset install — runs through the
 * local SoundHub Agent (127.0.0.1:8765) via AgentClient, so the realtime
 * audio thread is never touched.
 */
class SoundHubAudioProcessor final : public juce::AudioProcessor
{
public:
    SoundHubAudioProcessor();
    ~SoundHubAudioProcessor() override = default;

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;
    void processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "SoundHub"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int index) override { juce::ignoreUnused (index); }
    const juce::String getProgramName (int index) override { return juce::ignoreUnused (index), "Default"; }
    void changeProgramName (int index, const juce::String& newName) override { juce::ignoreUnused (index, newName); }

    void getStateInformation (juce::MemoryBlock& destData) override { juce::ignoreUnused (destData); }
    void setStateInformation (const void* data, int sizeInBytes) override { juce::ignoreUnused (data, sizeInBytes); }

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SoundHubAudioProcessor)
};

} // namespace soundhub
