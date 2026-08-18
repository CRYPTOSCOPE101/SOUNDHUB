#pragma once

#include <atomic>
#include <utility>

#include <juce_gui_basics/juce_gui_basics.h>
#include "AgentClient.h"

namespace soundhub
{

class SoundHubAudioProcessor;

/** The SoundHub companion panel: status, push, review/comments, catalog.
 *
 * All network calls run on detached juce::Thread workers (never the audio
 * thread, never the message thread) and hop back onto the message thread
 * with MessageManager::callAsync through a SafePointer guard.
 */
class SoundHubAudioProcessorEditor final : public juce::AudioProcessorEditor,
                                           public juce::ListBoxModel,
                                           private juce::Timer
{
public:
    explicit SoundHubAudioProcessorEditor (SoundHubAudioProcessor& owner);
    ~SoundHubAudioProcessorEditor() override;

    void paint (juce::Graphics& g) override;
    void resized() override;

    // juce::ListBoxModel
    int getNumRows() override;
    void paintListBoxItem (int rowNumber, juce::Graphics& g, int width, int height, bool rowIsSelected) override;

    // juce::Timer (initial status refresh)
    void timerCallback() override;

private:
    // ---- worker helpers: run off-thread, hop back safely ----------------
    template <typename Fn>
    void runOffThread (Fn&& fn);

    void refreshStatus();
    void doPush();
    void browseProjectFile();
    void browseMasterFile();
    void doOpenReview();
    void loadComments();
    void searchAssets();
    void installSelected();
    void log (const juce::String& line);
    void setStatus (const juce::String& text);

    SoundHubAudioProcessor& proc;
    AgentClient agent;
    std::atomic<bool> alive { true };

    // header / agent
    juce::Label titleLabel;
    juce::Label agentLabel;
    juce::TextEditor agentUrl;
    juce::TextButton connectButton;
    juce::Label statusLine;

    // push
    juce::Label pushLabel;
    juce::TextEditor projectFile;
    juce::TextButton browseProjectButton;
    juce::TextEditor masterFile;
    juce::TextButton browseMasterButton;
    juce::TextEditor projectName;
    juce::TextEditor branchName;
    juce::TextButton pushButton;

    // review
    juce::Label reviewLabel;
    juce::TextEditor shareToken;
    juce::TextButton commentsButton;
    juce::TextButton openButton;

    // catalog
    juce::Label catalogLabel;
    juce::TextEditor searchQuery;
    juce::TextButton searchButton;
    juce::ListBox assetsList;
    juce::TextButton installButton;

    // log
    juce::Label logLabel;
    juce::TextEditor logBox;

    juce::Array<juce::var> assets;
    juce::String lastReviewUrl;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SoundHubAudioProcessorEditor)
};

} // namespace soundhub
