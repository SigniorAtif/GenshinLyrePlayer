#nullable enable
using System;

namespace GenshinLyreMidiPlayer.WPF.ModernWPF;

public class CaptionedObject<T>
{
    public CaptionedObject(T o, string? caption = null)
    {
        Object  = o;
        Caption = caption;
    }

    public T Object { get; }

    protected string? Caption { get; }

    public override string ToString() => Caption ?? base.ToString() ?? string.Empty;
}

