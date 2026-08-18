#include "PluginProcessor.h"
#include "PluginEditor.h"

namespace soundhub
{

SoundHubAudioProcessor::SoundHubAudioProcessor()
    : AudioProcessor (BusesProperties().withInput ("Input", juce::AudioChannelSet::stereo, true)
                                          .withOutput ("Output", juce::AudioChannelSet::stereo, true))
{
}

void SoundHubAudioProcessor::prepareToPlay (double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused (sampleRate, samplesPerBlock);
}

void SoundHubAudioProcessor::releaseResources()
{
}

bool SoundHubAudioProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    // The plugin passes audio through untouched; any layout is fine.
    return layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo()
        || layouts.getMainOutputChannelSet() == juce::AudioChannelSet::mono();
}

void SoundHubAudioProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    // Companion panel — no DSP. The buffer passes through unchanged.
    juce::ignoreUnused (buffer, midiMessages);
}

juce::AudioProcessorEditor* SoundHubAudioProcessor::createEditor()
{
    return new SoundHubAudioProcessorEditor (*this);
}

} // namespace soundhub

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new soundhub::SoundHubAudioProcessor();
}
