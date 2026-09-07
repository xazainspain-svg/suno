#pragma once

#include "PluginProcessor.h"

class SunoBridgeAudioProcessorEditor : public juce::AudioProcessorEditor,
                                        private juce::Timer
{
public:
    explicit SunoBridgeAudioProcessorEditor (SunoBridgeAudioProcessor&);
    ~SunoBridgeAudioProcessorEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override; // refreshes the "loaded file" label
    void chooseFolder();
    void chooseFile();

    SunoBridgeAudioProcessor& processor;

    juce::Label titleLabel;
    juce::Label folderLabel;
    juce::TextEditor folderPathEditor;
    juce::TextButton browseFolderButton { "Browse folder..." };
    juce::TextButton loadFileButton { "Load one file..." };

    juce::Label statusLabel;
    juce::TextButton previewButton { "Preview" };

    juce::Label gainLabel;
    juce::Slider gainSlider;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> gainAttachment;

    std::unique_ptr<juce::FileChooser> fileChooser;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SunoBridgeAudioProcessorEditor)
};
