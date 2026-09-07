#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include <juce_dsp/juce_dsp.h>
#include <atomic>
#include <array>

/**
    SunoBridge
    ----------
    A one-shot "trigger pad" instrument plugin.

    It watches a folder on disk (where you export/download tracks or stems
    from Suno Studio) and automatically loads the most recently modified
    .wav/.aiff/.flac file it finds there. Any MIDI note-on then plays that
    sample from the start (velocity controls level), so the newest Suno
    export is instantly triggerable from an FL Studio channel without
    manually dragging the file in every time.

    This is a file-bridge, not a live generator: it never talks to Suno
    directly (there is no public Suno API), it just closes the gap between
    "I exported a WAV from Suno Studio" and "it's playable inside FL Studio".
*/
class SunoBridgeAudioProcessor : public juce::AudioProcessor,
                                  private juce::Timer
{
public:
    SunoBridgeAudioProcessor();
    ~SunoBridgeAudioProcessor() override;

    //==============================================================================
    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;
    using juce::AudioProcessor::processBlock;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    //==============================================================================
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    //==============================================================================
    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}

    //==============================================================================
    void getStateInformation (juce::MemoryBlock& destData) override;
    void setStateInformation (const void* data, int sizeInBytes) override;

    //==============================================================================
    // Called from the UI thread.
    void setWatchFolder (const juce::File& folder);
    juce::File getWatchFolder() const { return watchFolder; }

    void loadSpecificFile (const juce::File& file);

    juce::String getLoadedFileName() const { return loadedFileName.get(); }
    bool isSampleLoaded() const { return sampleLoaded.load(); }

    // Manual preview trigger (from the UI "Preview" button).
    void triggerPreview();

    juce::AudioProcessorValueTreeState apvts;

private:
    //==============================================================================
    void timerCallback() override; // polls the watch folder once a second
    void loadFileIntoSample (const juce::File& file); // runs on message thread
    juce::File findNewestAudioFile() const;

    //==============================================================================
    struct Voice
    {
        bool active = false;
        double position = 0.0;
        float gain = 1.0f;
    };

    static constexpr int maxVoices = 8;
    std::array<Voice, maxVoices> voices;

    void startVoice (float velocityGain);

    //==============================================================================
    juce::AudioFormatManager formatManager;
    juce::CriticalSection sampleLock; // guards sampleBuffer + sampleSourceRate swap
    juce::AudioBuffer<float> sampleBuffer;
    double sampleSourceRate = 44100.0;
    double currentSampleRate = 44100.0;
    std::atomic<bool> sampleLoaded { false };

    juce::File watchFolder;
    juce::File lastLoadedFile;
    juce::Time lastLoadedFileTime;

    // Simple thread-safe-ish string holder for the UI to poll.
    struct AtomicString
    {
        void set (const juce::String& s) { juce::ScopedLock l (lock); value = s; }
        juce::String get() const { juce::ScopedLock l (lock); return value; }
        mutable juce::CriticalSection lock;
        juce::String value;
    };
    AtomicString loadedFileName;

    std::atomic<bool> previewRequested { false };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SunoBridgeAudioProcessor)
};
