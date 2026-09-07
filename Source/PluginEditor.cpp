#include "PluginProcessor.h"
#include "PluginEditor.h"

SunoBridgeAudioProcessorEditor::SunoBridgeAudioProcessorEditor (SunoBridgeAudioProcessor& p)
    : AudioProcessorEditor (&p), processor (p)
{
    titleLabel.setText ("SunoBridge", juce::dontSendNotification);
    titleLabel.setFont (juce::Font (22.0f, juce::Font::bold));
    titleLabel.setJustificationType (juce::Justification::centredLeft);
    addAndMakeVisible (titleLabel);

    folderLabel.setText ("Watch folder (newest .wav/.aiff/.flac is auto-loaded):",
                          juce::dontSendNotification);
    folderLabel.setFont (juce::Font (13.0f));
    addAndMakeVisible (folderLabel);

    folderPathEditor.setText (processor.getWatchFolder().getFullPathName(), juce::dontSendNotification);
    folderPathEditor.setReadOnly (true);
    addAndMakeVisible (folderPathEditor);

    browseFolderButton.onClick = [this] { chooseFolder(); };
    addAndMakeVisible (browseFolderButton);

    loadFileButton.onClick = [this] { chooseFile(); };
    addAndMakeVisible (loadFileButton);

    statusLabel.setText ("No file loaded yet", juce::dontSendNotification);
    statusLabel.setFont (juce::Font (14.0f, juce::Font::italic));
    addAndMakeVisible (statusLabel);

    previewButton.onClick = [this] { processor.triggerPreview(); };
    addAndMakeVisible (previewButton);

    gainLabel.setText ("Gain", juce::dontSendNotification);
    addAndMakeVisible (gainLabel);

    gainSlider.setSliderStyle (juce::Slider::LinearHorizontal);
    gainSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 60, 20);
    addAndMakeVisible (gainSlider);
    gainAttachment = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment> (
        processor.apvts, "gain", gainSlider);

    setSize (480, 260);
    startTimerHz (4);
}

SunoBridgeAudioProcessorEditor::~SunoBridgeAudioProcessorEditor() = default;

void SunoBridgeAudioProcessorEditor::chooseFolder()
{
    fileChooser = std::make_unique<juce::FileChooser> (
        "Choose the folder where Suno Studio exports land",
        processor.getWatchFolder());

    const auto chooserFlags = juce::FileBrowserComponent::openMode
                             | juce::FileBrowserComponent::canSelectDirectories;

    fileChooser->launchAsync (chooserFlags, [this] (const juce::FileChooser& fc)
    {
        const auto result = fc.getResult();
        if (result != juce::File())
        {
            processor.setWatchFolder (result);
            folderPathEditor.setText (result.getFullPathName(), juce::dontSendNotification);
        }
    });
}

void SunoBridgeAudioProcessorEditor::chooseFile()
{
    fileChooser = std::make_unique<juce::FileChooser> (
        "Load a specific exported file",
        processor.getWatchFolder(),
        "*.wav;*.aiff;*.aif;*.flac");

    fileChooser->launchAsync (juce::FileBrowserComponent::openMode
                                   | juce::FileBrowserComponent::canSelectFiles,
                               [this] (const juce::FileChooser& fc)
    {
        const auto result = fc.getResult();
        if (result != juce::File())
            processor.loadSpecificFile (result);
    });
}

void SunoBridgeAudioProcessorEditor::timerCallback()
{
    statusLabel.setText (processor.isSampleLoaded()
                              ? "Loaded: " + processor.getLoadedFileName()
                              : "No file loaded yet",
                          juce::dontSendNotification);
}

void SunoBridgeAudioProcessorEditor::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (0xff1e1e24));
}

void SunoBridgeAudioProcessorEditor::resized()
{
    auto area = getLocalBounds().reduced (16);

    titleLabel.setBounds (area.removeFromTop (30));
    area.removeFromTop (10);

    folderLabel.setBounds (area.removeFromTop (18));
    folderPathEditor.setBounds (area.removeFromTop (26));
    area.removeFromTop (6);

    auto buttonRow = area.removeFromTop (28);
    browseFolderButton.setBounds (buttonRow.removeFromLeft (150));
    buttonRow.removeFromLeft (8);
    loadFileButton.setBounds (buttonRow.removeFromLeft (150));

    area.removeFromTop (14);
    statusLabel.setBounds (area.removeFromTop (22));
    area.removeFromTop (10);

    auto gainRow = area.removeFromTop (26);
    gainLabel.setBounds (gainRow.removeFromLeft (50));
    gainSlider.setBounds (gainRow);

    area.removeFromTop (14);
    previewButton.setBounds (area.removeFromTop (30).removeFromLeft (120));
}
