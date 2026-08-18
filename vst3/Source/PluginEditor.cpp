#include "PluginEditor.h"
#include "PluginProcessor.h"

namespace soundhub
{

SoundHubAudioProcessorEditor::SoundHubAudioProcessorEditor (SoundHubAudioProcessor& owner)
    : AudioProcessorEditor (owner),
      proc (owner)
{
    setSize (640, 780);

    titleLabel.setText ("SoundHub — VST3 companion", juce::dontSendNotification);
    titleLabel.setFont (juce::Font (juce::FontOptions (17.0f).setStyleFlags (juce::Font::bold)));
    addAndMakeVisible (titleLabel);

    agentLabel.setText ("Agent", juce::dontSendNotification);
    addAndMakeVisible (agentLabel);
    agentUrl.setText ("http://127.0.0.1:8765", juce::dontSendNotification);
    addAndMakeVisible (agentUrl);
    connectButton.setButtonText ("Connect");
    connectButton.onClick = [this] { agent.setBaseUrl (agentUrl.getText()); refreshStatus(); };
    addAndMakeVisible (connectButton);

    statusLine.setColour (juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible (statusLine);

    pushLabel.setText ("Push project to SoundHub (renders master/stems in the DAW first)", juce::dontSendNotification);
    pushLabel.setFont (juce::Font (juce::FontOptions (14.0f).setStyleFlags (juce::Font::bold)));
    addAndMakeVisible (pushLabel);

    projectFile.setTooltip ("Absolute path to the DAW project file (.cpr / .flp / .als / .rpp)");
    addAndMakeVisible (projectFile);
    browseProjectButton.setButtonText ("Browse…");
    browseProjectButton.onClick = [this] { browseProjectFile(); };
    addAndMakeVisible (browseProjectButton);

    masterFile.setTooltip ("Optional master export (wav/mp3) — opens a review session with gapless A/B");
    addAndMakeVisible (masterFile);
    browseMasterButton.setButtonText ("Browse…");
    browseMasterButton.onClick = [this] { browseMasterFile(); };
    addAndMakeVisible (browseMasterButton);

    projectName.setText ("", juce::dontSendNotification);
    projectName.setTooltip ("Project name (auto-created on first push)");
    addAndMakeVisible (projectName);
    branchName.setText ("main", juce::dontSendNotification);
    branchName.setTooltip ("Branch, e.g. review/v12");
    addAndMakeVisible (branchName);
    pushButton.setButtonText ("Push");
    pushButton.onClick = [this] { doPush(); };
    addAndMakeVisible (pushButton);

    reviewLabel.setText ("Review & comments", juce::dontSendNotification);
    reviewLabel.setFont (juce::Font (juce::FontOptions (14.0f).setStyleFlags (juce::Font::bold)));
    addAndMakeVisible (reviewLabel);

    shareToken.setTooltip ("The /r/<token> part of a review link, e.g. demo-review-token");
    addAndMakeVisible (shareToken);
    commentsButton.setButtonText ("Comments");
    commentsButton.onClick = [this] { loadComments(); };
    addAndMakeVisible (commentsButton);
    openButton.setButtonText ("Open review");
    openButton.onClick = [this] { doOpenReview(); };
    addAndMakeVisible (openButton);

    catalogLabel.setText ("Marketplace catalog", juce::dontSendNotification);
    catalogLabel.setFont (juce::Font (juce::FontOptions (14.0f).setStyleFlags (juce::Font::bold)));
    addAndMakeVisible (catalogLabel);

    searchQuery.setText ("", juce::dontSendNotification);
    searchQuery.setTooltip ("Search the catalog, e.g. \"dark bass\"");
    addAndMakeVisible (searchQuery);
    searchButton.setButtonText ("Search");
    searchButton.onClick = [this] { searchAssets(); };
    addAndMakeVisible (searchButton);

    assetsList.setModel (this);
    addAndMakeVisible (assetsList);
    installButton.setButtonText ("Install selected (Agent cache)");
    installButton.onClick = [this] { installSelected(); };
    addAndMakeVisible (installButton);

    logLabel.setText ("Log", juce::dontSendNotification);
    logLabel.setFont (juce::Font (juce::FontOptions (14.0f).setStyleFlags (juce::Font::bold)));
    addAndMakeVisible (logLabel);

    logBox.setMultiLine (true);
    logBox.setReadOnly (true);
    logBox.setScrollbarsShown (true);
    logBox.setCaretVisible (false);
    addAndMakeVisible (logBox);

    log ("Connect to the Agent, then pick a project file and push — or paste a /r/<token> for comments.");
    startTimer (600);
}

SoundHubAudioProcessorEditor::~SoundHubAudioProcessorEditor()
{
    alive = false;
}

void SoundHubAudioProcessorEditor::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colours::white);
}

// ---------- worker helper ----------

template <typename Fn>
void SoundHubAudioProcessorEditor::runOffThread (Fn&& fn)
{
    // Copy everything the worker needs up front so it never derefs `this`.
    const auto base = agent.getBaseUrl();
    juce::Component::SafePointer<SoundHubAudioProcessorEditor> safeThis (this);
    juce::Thread::launch ([base, safeThis, work = std::forward<Fn> (fn)]() mutable
    {
        AgentClient local (base);
        work (local, safeThis);
    });
}

// ---------- actions ----------

void SoundHubAudioProcessorEditor::refreshStatus()
{
    setStatus ("connecting…");
    runOffThread ([](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.status();
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            if (r.ok)
                safe->setStatus ("Agent OK · " + r.json.getProperty ("user", "?").toString()
                                 + " · " + juce::String (static_cast<int> (r.json.getProperty ("cached_assets", 0))) + " cached asset(s)");
            else
                safe->setStatus ("Agent unreachable — run `snd agent` in backend/ (error: " + r.error + ")");
        });
    });
}

void SoundHubAudioProcessorEditor::browseProjectFile()
{
    juce::FileChooser fc ("Choose the DAW project file", juce::File::getSpecialLocation (juce::File::userHomeDirectory),
                          "*.cpr;*.cprx;*.flp;*.als;*.rpp");
    if (fc.browseForFileToOpen())
        projectFile.setText (fc.getResult().getFullPathName(), juce::dontSendNotification);
}

void SoundHubAudioProcessorEditor::browseMasterFile()
{
    juce::FileChooser fc ("Choose the rendered master", juce::File::getSpecialLocation (juce::File::userHomeDirectory),
                          "*.wav;*.mp3;*.flac;*.aif;*.aiff;*.m4a;*.ogg");
    if (fc.browseForFileToOpen())
        masterFile.setText (fc.getResult().getFullPathName(), juce::dontSendNotification);
}

void SoundHubAudioProcessorEditor::doPush()
{
    const auto target = projectFile.getText().trim();
    if (target.isEmpty())
    {
        log ("Push: no project file selected — pick the .cpr / .flp first.");
        return;
    }
    const auto project = projectName.getText().trim();
    const auto branch = branchName.getText().trim().isEmpty() ? juce::String ("main") : branchName.getText().trim();
    const auto master = masterFile.getText().trim();
    log ("Pushing " + target + " …");
    pushButton.setEnabled (false);

    runOffThread ([target, project, branch, master](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.push (target, project, branch, "pushed from SoundHub VST3", master, {});
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            safe->pushButton.setEnabled (true);
            if (r.ok)
            {
                safe->lastReviewUrl = r.json.getProperty ("review_url", "").toString();
                safe->log ("✓ pushed — commit #" + r.json.getProperty ("commit_id", "?").toString()
                           + " · " + r.json.getProperty ("branch", "").toString()
                           + (safe->lastReviewUrl.isNotEmpty() ? "\n  review: " + safe->lastReviewUrl : ""));
                if (r.json.getProperty ("uploaded", juce::var()).isObject())
                    safe->log ("  uploaded: " + juce::JSON::toString (r.json.getProperty ("uploaded", juce::var())));

            }
            else
            {
                safe->log ("Push failed: " + r.error);
            }
        });
    });
}

void SoundHubAudioProcessorEditor::doOpenReview()
{
    const auto token = shareToken.getText().trim();
    const auto url = token.isNotEmpty() && ! token.startsWith ("http")
        ? juce::String ("http://localhost:5173/r/") + token
        : (lastReviewUrl.isNotEmpty() ? lastReviewUrl : token);
    if (url.isEmpty() || (! url.startsWith ("http://") && ! url.startsWith ("https://")))
    {
        log ("Open review: paste a /r/<token> (or push once to get a review URL).");
        return;
    }
    log ("Opening " + url + " in the browser…");
    runOffThread ([url](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.openReview (url);
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            safe->log (r.ok ? "✓ review opened in the browser" : "Open failed: " + r.error);
        });
    });
}

void SoundHubAudioProcessorEditor::loadComments()
{
    const auto token = shareToken.getText().trim();
    if (token.isEmpty())
    {
        log ("Comments: paste the /r/<token> of a review session first.");
        return;
    }
    log ("Fetching open comments for " + token + " …");
    runOffThread ([token](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.comments (token, "markdown");
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            if (r.ok)
                safe->log ("— open comments —\n" + r.text);
            else
                safe->log ("Comments failed: " + r.error);
        });
    });
}

void SoundHubAudioProcessorEditor::searchAssets()
{
    const auto q = searchQuery.getText().trim();
    log ("Searching catalog" + (q.isNotEmpty() ? (": \"" + q + "\"") : juce::String ("…")));
    runOffThread ([q](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.searchAssets (q, 0, 0, {});
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            safe->assets.clear();
            if (r.ok && r.json.getProperty ("items", juce::var()).isArray())
            {
                auto items = r.json.getProperty ("items", juce::var());
                for (int i = 0; i < items.size(); ++i)
                    safe->assets.add (items[i]);
                safe->log ("✓ " + juce::String (safe->assets.size()) + " asset(s) — select one and install.");
            }
            else
            {
                safe->log ("Search failed: " + r.error);
            }
            safe->assetsList.updateContent();
        });
    });
}

void SoundHubAudioProcessorEditor::installSelected()
{
    const int row = assetsList.getSelectedRow();
    if (row < 0 || row >= assets.size())
    {
        log ("Install: select an asset from the list first.");
        return;
    }
    const auto item = assets[row];
    const int listingId = static_cast<int> (item.getProperty ("listing_id", 0));
    const auto name = item.getProperty ("name", "?").toString();
    log ("Installing \"" + name + "\" (id " + juce::String (listingId) + ") into the Agent cache…");
    installButton.setEnabled (false);

    runOffThread ([listingId](AgentClient& local, juce::Component::SafePointer<SoundHubAudioProcessorEditor> safe)
    {
        const auto r = local.installAsset (listingId, {});
        juce::MessageManager::callAsync ([safe, r]
        {
            if (safe == nullptr)
                return;
            safe->installButton.setEnabled (true);
            if (r.ok)
                safe->log ("✓ installed → " + r.json.getProperty ("cached_path", "").toString()
                           + " · license: " + r.json.getProperty ("license", "").toString());
            else
                safe->log ("Install failed: " + r.error);
        });
    });
}

// ---------- ListBox model ----------

int SoundHubAudioProcessorEditor::getNumRows()
{
    return assets.size();
}

void SoundHubAudioProcessorEditor::paintListBoxItem (int rowNumber, juce::Graphics& g, int width, int height, bool rowIsSelected)
{
    if (rowNumber < 0 || rowNumber >= assets.size())
        return;
    const auto& item = assets[rowNumber];
    g.fillAll (rowIsSelected ? juce::Colours::lightblue : juce::Colours::white);
    g.setColour (juce::Colours::black);
    const auto line = item.getProperty ("listing_id", "?").toString() + "  "
                    + item.getProperty ("name", "?").toString() + "  ["
                    + item.getProperty ("format", "?").toString() + "]  "
                    + item.getProperty ("price_snd", "?").toString() + " SND · "
                    + item.getProperty ("license", "?").toString();
    g.drawText (line, 4, 0, width - 8, height, juce::Justification::centredLeft, true);
}

// ---------- misc ----------

void SoundHubAudioProcessorEditor::log (const juce::String& line)
{
    logBox.moveCaretToEnd();
    logBox.insertTextAtCaret (line + "\n");
}

void SoundHubAudioProcessorEditor::setStatus (const juce::String& text)
{
    statusLine.setText (text, juce::dontSendNotification);
}

void SoundHubAudioProcessorEditor::timerCallback()
{
    stopTimer();
    refreshStatus();
}

void SoundHubAudioProcessorEditor::resized()
{
    auto area = getLocalBounds().reduced (12);
    auto row = [&area](int h) -> juce::Rectangle<int>
    {
        auto r = area.removeFromTop (h);
        area.removeFromTop (6);
        return r;
    };

    titleLabel.setBounds (row (22));
    {
        auto r = row (26);
        agentLabel.setBounds (r.removeFromLeft (52));
        agentUrl.setBounds (r.removeFromLeft (r.getWidth() - 120));
        connectButton.setBounds (r);
    }
    statusLine.setBounds (row (20));

    pushLabel.setBounds (row (22));
    {
        auto r = row (26);
        projectFile.setBounds (r.removeFromLeft (r.getWidth() - 90));
        browseProjectButton.setBounds (r);
    }
    {
        auto r = row (26);
        masterFile.setBounds (r.removeFromLeft (r.getWidth() - 90));
        browseMasterButton.setBounds (r);
    }
    {
        auto r = row (26);
        projectName.setBounds (r.removeFromLeft (r.getWidth() / 2 - 4));
        branchName.setBounds (r);
    }
    pushButton.setBounds (row (30));

    reviewLabel.setBounds (row (22));
    {
        auto r = row (26);
        shareToken.setBounds (r.removeFromLeft (r.getWidth() - 170));
        commentsButton.setBounds (r.removeFromLeft (90));
        openButton.setBounds (r);
    }

    catalogLabel.setBounds (row (22));
    {
        auto r = row (26);
        searchQuery.setBounds (r.removeFromLeft (r.getWidth() - 90));
        searchButton.setBounds (r);
    }
    assetsList.setBounds (row (140));
    installButton.setBounds (row (28));

    logLabel.setBounds (row (22));
    logBox.setBounds (area);
}

} // namespace soundhub
