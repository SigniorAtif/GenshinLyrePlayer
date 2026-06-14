using Stylet;

namespace GenshinLyreMidiPlayer.WPF.Core;

/// <summary>
/// Represents one of the 21 Windsong Lyre keys for the visualizer keyboard grid.
/// <see cref="IsActive"/> is toggled each tick by LyrePlayerViewModel;
/// PropertyChanged.Fody wires up change notification automatically.
/// </summary>
public class LyreKeyViewModel : PropertyChangedBase
{
    public string Key      { get; }
    public bool   IsActive { get; set; }

    public LyreKeyViewModel(string key) => Key = key;
}
