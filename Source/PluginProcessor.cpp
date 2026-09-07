#include "PluginProcessor.h"
#include "PluginEditor.h"

namespace
{
    constexpr const char* kStateFolderKey = "watchFolder";
    constexpr const char* kStateGainId    = "gain";
}

//==============================================================================
SunoBridgeAudioProcessor::SunoBridgeAudioProcessor()
    : juce::AudioProcessor (BusesProperties()
                                 .withOutput ("Output", juce::AudioChannelSet::stereo(), true)),
      apvts (*this, nullptr, "PARAMS",
             { std::make_unique<juce::AudioParameterFloat> (
                   juce::ParameterID { kStateGainId, 1 }, "Gain",
                   juce::NormalisableRange<float> (0.0f, 1.5f, 0.001f), 1.0f) })
{
    formatManager.registerBasicFormats();

    // Default watch folder: guess a sensible spot; the user can change it
    // from the plugin UI. Falls back to the Downloads folder.
    watchFolder = juce::File::getSpecialLocation (juce::File::userHomeDirectory)
                      .getChildFile ("Downloads");

    startTimer (1000); // poll the watch folder once a second
}

SunoBridgeAudioProcessor::~SunoBridgeAudioProcessor()
{
    stopTimer();
}

//==============================================================================
void SunoBridgeAudioProcessor::prepareToPlay (double sampleRate, int /*samplesPerBlock*/)
{
    currentSampleRate = sampleRate;
    for (auto& v : voices)
        v = Voice {};
}

void SunoBridgeAudioProcessor::releaseResources() {}

bool SunoBridgeAudioProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    return layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo();
}

//==============================================================================
juce::File SunoBridgeAudioProcessor::findNewestAudioFile() const
{
    if (! watchFolder.isDirectory())
        return {};

    juce::File newest;
    juce::Time newestTime;

    for (const auto& entry : juce::RangedDirectoryIterator (watchFolder, false, "*.wav;*.aiff;*.aif;*.flac"))
    {
        const auto f = entry.getFile();
        const auto t = f.getLastModificationTime();
        if (newest == juce::File() || t > newestTime)
        {
            newest = f;
            newestTime = t;
        }
    }
    return newest;
}

void SunoBridgeAudioProcessor::timerCallback()
{
    const auto candidate = findNewestAudioFile();
    if (candidate != juce::File() && candidate != lastLoadedFile)
        loadFileIntoSample (candidate);
}

void SunoBridgeAudioProcessor::loadFileIntoSample (const juce::File& file)
{
    std::unique_ptr<juce::AudioFormatReader> reader (formatManager.createReaderFor (file));
    if (reader == nullptr)
        return;

    const auto numSamples = (int) juce::jmin ((juce::int64) reader->lengthInSamples,
                                                (juce::int64) 1 << 26); // safety cap (~1.3 min @ 48k stereo... generous)
    juce::AudioBuffer<float> newBuffer ((int) reader->numChannels, numSamples);
    reader->read (&newBuffer, 0, numSamples, 0, true, true);

    {
        const juce::ScopedLock sl (sampleLock);
        sampleBuffer = std::move (newBuffer);
        sampleSourceRate = reader->sampleRate;
    }

    lastLoadedFile = file;
    lastLoadedFileTime = file.getLastModificationTime();
    loadedFileName.set (file.getFileName());
    sampleLoaded.store (true);

    for (auto& v : voices)
        v.active = false;
}

void SunoBridgeAudioProcessor::setWatchFolder (const juce::File& folder)
{
    watchFolder = folder;
    lastLoadedFile = juce::File(); // force a rescan/reload next timer tick
}

void SunoBridgeAudioProcessor::loadSpecificFile (const juce::File& file)
{
    loadFileIntoSample (file);
}

void SunoBridgeAudioProcessor::triggerPreview()
{
    previewRequested.store (true);
}

//==============================================================================
void SunoBridgeAudioProcessor::startVoice (float velocityGain)
{
    // Steal the oldest inactive voice, or the first voice if all are busy.
    for (auto& v : voices)
    {
        if (! v.active)
        {
            v.active = true;
            v.position = 0.0;
            v.gain = velocityGain;
            return;
        }
    }
    voices[0].active = true;
    voices[0].position = 0.0;
    voices[0].gain = velocityGain;
}

void SunoBridgeAudioProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    juce::ScopedNoDenormals noDenormals;
    buffer.clear();

    if (previewRequested.exchange (false))
        startVoice (1.0f);

    for (const auto metadata : midiMessages)
    {
        const auto msg = metadata.getMessage();
        if (msg.isNoteOn())
            startVoice (msg.getFloatVelocity());
    }

    if (! sampleLoaded.load())
        return;

    const juce::ScopedLock sl (sampleLock);
    if (sampleBuffer.getNumSamples() == 0)
        return;

    const double ratio = sampleSourceRate / currentSampleRate;
    const float gainParam = apvts.getRawParameterValue (kStateGainId)->load();
    const int outChannels = buffer.getNumChannels();
    const int srcChannels = sampleBuffer.getNumChannels();
    const int numBlockSamples = buffer.getNumSamples();

    for (auto& v : voices)
    {
        if (! v.active)
            continue;

        for (int i = 0; i < numBlockSamples; ++i)
        {
            const int srcIndexInt = (int) v.position;
            if (srcIndexInt >= sampleBuffer.getNumSamples() - 1)
            {
                v.active = false;
                break;
            }

            const float frac = (float) (v.position - (double) srcIndexInt);

            for (int ch = 0; ch < outChannels; ++ch)
            {
                const int srcCh = juce::jmin (ch, srcChannels - 1);
                const float s0 = sampleBuffer.getSample (srcCh, srcIndexInt);
                const float s1 = sampleBuffer.getSample (srcCh, srcIndexInt + 1);
                const float sample = s0 + frac * (s1 - s0);
                buffer.addSample (ch, i, sample * v.gain * gainParam);
            }

            v.position += ratio;
        }
    }
}

//==============================================================================
void SunoBridgeAudioProcessor::getStateInformation (juce::MemoryBlock& destData)
{
    auto state = apvts.copyState();
    state.setProperty (kStateFolderKey, watchFolder.getFullPathName(), nullptr);
    std::unique_ptr<juce::XmlElement> xml (state.createXml());
    copyXmlToBinary (*xml, destData);
}

void SunoBridgeAudioProcessor::setStateInformation (const void* data, int sizeInBytes)
{
    std::unique_ptr<juce::XmlElement> xml (getXmlFromBinary (data, sizeInBytes));
    if (xml == nullptr)
        return;

    auto state = juce::ValueTree::fromXml (*xml);
    if (! state.isValid())
        return;

    apvts.replaceState (state);

    const auto folderPath = state.getProperty (kStateFolderKey, juce::String());
    if (folderPath.toString().isNotEmpty())
        setWatchFolder (juce::File (folderPath.toString()));
}

//==============================================================================
juce::AudioProcessorEditor* SunoBridgeAudioProcessor::createEditor()
{
    return new SunoBridgeAudioProcessorEditor (*this);
}

//==============================================================================
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new SunoBridgeAudioProcessor();
}
