#include "AgentClient.h"

namespace soundhub
{

AgentClient::AgentClient (const juce::String& agentBaseUrl)
    : baseUrl (agentBaseUrl.trimCharactersEnd ("/"))
{
}

AgentClient::Response AgentClient::perform (const juce::String& method, const juce::String& path,
                                           const juce::String& query, const juce::String& body)
{
    Response r;
    auto fullUrl = baseUrl + path;
    if (query.isNotEmpty())
        fullUrl += "?" + query;

    auto url = juce::URL (fullUrl);
    if (method == "POST" && body.isNotEmpty())
        url = url.withPOSTData (body);

    // `true` = send URL parameters (here: the JSON body) in the request body
    // and use the POST command; `false` = plain GET.
    juce::WebInputStream stream (url, method == "POST");
    stream.withConnectionTimeout (15000);
    if (method == "POST")
        stream.withExtraHeaders ("Content-Type: application/json");

    const auto text = stream.readEntireStreamAsString();
    r.status = stream.getStatusCode();

    // Parse JSON bodies (catalog, push contract, status, ...).
    const auto trimmed = text.trim();
    if (trimmed.isNotEmpty() && (trimmed.startsWithChar ('{') || trimmed.startsWithChar ('[')))
    {
        const auto parsed = juce::JSON::parse (trimmed);
        if (parsed.isObject() || parsed.isArray())
            r.json = parsed;
    }

    if (r.status >= 200 && r.status < 300)
    {
        r.ok = true;
        if (r.json.isObject() && r.json.hasProperty ("ok"))
            r.ok = static_cast<bool> (r.json.getProperty ("ok"));
        if (! r.ok)
            r.error = r.json.getProperty ("error", "Agent returned ok=false").toString();
    }
    else
    {
        r.error = r.json.isObject()
            ? r.json.getProperty ("error", "HTTP " + juce::String (r.status)).toString()
            : "HTTP " + juce::String (r.status);
    }
    r.text = text;
    return r;
}

AgentClient::Response AgentClient::get (const juce::String& path, const juce::String& query)
{
    return perform ("GET", path, query, {});
}

AgentClient::Response AgentClient::postJson (const juce::String& path, const juce::var& body)
{
    return perform ("POST", path, {}, juce::JSON::toString (body));
}

AgentClient::Response AgentClient::health()
{
    return get ("/health");
}

AgentClient::Response AgentClient::status()
{
    return get ("/status");
}

AgentClient::Response AgentClient::push (const juce::String& target, const juce::String& project,
                                        const juce::String& branch, const juce::String& message,
                                        const juce::String& audio, const juce::String& stems)
{
    juce::DynamicObject::Ptr body = new juce::DynamicObject();
    body->setProperty ("target", target);
    body->setProperty ("project", project);
    body->setProperty ("branch", branch);
    body->setProperty ("message", message);
    if (audio.isNotEmpty()) body->setProperty ("audio", audio);
    if (stems.isNotEmpty()) body->setProperty ("stems", stems);
    return postJson ("/push", juce::var (body.get()));
}

AgentClient::Response AgentClient::comments (const juce::String& shareToken, const juce::String& format)
{
    return get ("/comments", "token=" + shareToken + "&format=" + format);
}

AgentClient::Response AgentClient::reviews()
{
    return get ("/reviews");
}

AgentClient::Response AgentClient::searchAssets (const juce::String& query, int bpmMin, int bpmMax,
                                                const juce::String& genre)
{
    juce::StringArray parts;
    if (query.isNotEmpty()) parts.add ("q=" + query);
    if (bpmMin > 0)         parts.add ("bpm_min=" + juce::String (bpmMin));
    if (bpmMax > 0)         parts.add ("bpm_max=" + juce::String (bpmMax));
    if (genre.isNotEmpty()) parts.add ("genre=" + genre);
    return get ("/assets", parts.joinIntoString ("&"));
}

AgentClient::Response AgentClient::installAsset (int listingId, const juce::String& dir)
{
    juce::DynamicObject::Ptr body = new juce::DynamicObject();
    if (dir.isNotEmpty()) body->setProperty ("dir", dir);
    return postJson ("/assets/" + juce::String (listingId) + "/install", juce::var (body.get()));
}

AgentClient::Response AgentClient::openReview (const juce::String& reviewUrl)
{
    juce::DynamicObject::Ptr body = new juce::DynamicObject();
    body->setProperty ("url", reviewUrl);
    return postJson ("/open", juce::var (body.get()));
}

} // namespace soundhub
