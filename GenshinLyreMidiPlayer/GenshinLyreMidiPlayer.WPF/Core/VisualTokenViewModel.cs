using Stylet;

namespace GenshinLyreMidiPlayer.WPF.Core;

/// <summary>
/// One token chip in the full-song token stream.
/// <see cref="State"/> is mutated in-place each tick (Past / Current / Future);
/// PropertyChanged.Fody wires up change notification automatically so only
/// the two affected chips re-render instead of rebuilding the whole list.
/// </summary>
public class VisualTokenViewModel : PropertyChangedBase
{
    public string           Display { get; }
    public VisualTokenState State   { get; set; }

    public VisualTokenViewModel(string display)
    {
        Display = display;
        State   = VisualTokenState.Future;
    }
}
