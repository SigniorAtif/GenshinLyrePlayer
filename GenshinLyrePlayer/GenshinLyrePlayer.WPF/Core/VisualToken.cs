using System;

namespace GenshinLyreMidiPlayer.WPF.Core;

public enum VisualTokenState { Past, Current, Future }

/// <summary>
/// Pure timing data for one token — stored in the full timeline list.
/// State is tracked separately by <see cref="VisualTokenViewModel"/>.
/// </summary>
public record VisualToken(
    TimeSpan Start,
    TimeSpan End,
    string   Display,
    bool     IsRest
);
