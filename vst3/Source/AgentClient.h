#pragma once

#include <juce_core/juce_core.h>

namespace soundhub
{

/** Thin blocking HTTP/JSON client for the local SoundHub Agent.
 *
 * The Agent (started with `snd agent` in backend/) listens on
 * 127.0.0.1:8765 and owns the token, the push pipeline, the asset cache and
 * browser opening — this client only speaks JSON to it. Every method is
 * blocking and must run off the audio thread (use a juce::Thread / timer).
 *
 * Contract: JSON responses are {"ok": true|false, ...}; errors carry
 * "error". Non-JSON endpoints (comments export) come back in `text`.
 */
class AgentClient
{
public:
    explicit AgentClient (const juce::String& agentBaseUrl = "http://127.0.0.1:8765");

    void setBaseUrl (const juce::String& url) { baseUrl = url.trimCharactersEnd ("/"); }
    juce::String getBaseUrl() const noexcept { return baseUrl; }

    struct Response
    {
        bool ok = false;
        int status = 0;
        juce::var json;      // parsed JSON for application/json responses
        juce::String text;   // raw body otherwise (e.g. markdown comments)
        juce::String error;  // human-readable error when !ok
    };

    Response get (const juce::String& path, const juce::String& query = {});
    Response postJson (const juce::String& path, const juce::var& body);

    // ---- Agent endpoints ------------------------------------------------
    Response health();
    Response status();
    Response push (const juce::String& target, const juce::String& project,
                   const juce::String& branch, const juce::String& message,
                   const juce::String& audio = {}, const juce::String& stems = {});
    Response comments (const juce::String& shareToken, const juce::String& format = "markdown");
    Response reviews();
    Response searchAssets (const juce::String& query = {}, int bpmMin = 0, int bpmMax = 0,
                           const juce::String& genre = {});
    Response installAsset (int listingId, const juce::String& dir = {});
    Response openReview (const juce::String& reviewUrl);

private:
    Response perform (const juce::String& method, const juce::String& path,
                      const juce::String& query, const juce::String& body);

    juce::String baseUrl;
};

} // namespace soundhub
