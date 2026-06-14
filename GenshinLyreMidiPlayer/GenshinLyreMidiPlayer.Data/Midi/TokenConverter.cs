using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Interaction;

namespace GenshinLyreMidiPlayer.Data.Midi;

/// <summary>
/// Converts a Genshin Lyre token sheet (.txt) to an in-memory MIDI file
/// so the existing playback pipeline can handle it without modification.
///
/// Token format:
///   BPM 400
///   A S D/2 -/4 [QW]/2 ...
///
/// Letters are QWERTY keys (Z X C V B N M / A S D F G H J / Q W E R T Y U).
/// [ABC] denotes a chord. - is a rest. /N divides the beat by N.
/// </summary>
public static class TokenConverter
{
    // QWERTY key → MIDI note number, matching DefaultNotes order in Keyboard.cs
    // Row 1 (bottom): Z X C V B N M  →  C3 D3 E3 F3 G3 A3 B3  (48-59)
    // Row 2 (middle): A S D F G H J  →  C4 D4 E4 F4 G4 A4 B4  (60-71)
    // Row 3 (top):    Q W E R T Y U  →  C5 D5 E5 F5 G5 A5 B5  (72-83)
    private static readonly Dictionary<char, int> KeyToNote = new()
    {
        ['Z'] = 48, ['X'] = 50, ['C'] = 52, ['V'] = 53, ['B'] = 55, ['N'] = 57, ['M'] = 59,
        ['A'] = 60, ['S'] = 62, ['D'] = 64, ['F'] = 65, ['G'] = 67, ['H'] = 69, ['J'] = 71,
        ['Q'] = 72, ['W'] = 74, ['E'] = 76, ['R'] = 77, ['T'] = 79, ['Y'] = 81, ['U'] = 83
    };

    // Ticks per quarter note — matches the default resolution used throughout the app
    private const int Ppq = 480;

    public static Melanchall.DryWetMidi.Core.MidiFile ToMidi(string path)
    {
        var lines = File.ReadAllLines(path);
        var bpm   = 120;

        if (lines.Length > 0
            && lines[0].StartsWith("BPM ", StringComparison.OrdinalIgnoreCase)
            && int.TryParse(lines[0][4..].Trim(), out var parsed))
            bpm = parsed;

        var midiFile = new Melanchall.DryWetMidi.Core.MidiFile();
        midiFile.TimeDivision = new TicksPerQuarterNoteTimeDivision(Ppq);

        // Track 0 — tempo map
        var tempoTrack = new TrackChunk(new SetTempoEvent((long)(60_000_000.0 / bpm)));

        // Track 1 — notes
        var noteTrack = new TrackChunk();
        using (var mgr = noteTrack.ManageNotes())
        {
            long cursor = 0;
            foreach (var line in lines.Skip(1))
            {
                foreach (var token in line.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries))
                {
                    var (keys, ticks) = ParseToken(token);
                    foreach (var midiNote in keys)
                    {
                        mgr.Objects.Add(new Note(
                            (SevenBitNumber) midiNote,
                            length: Math.Max(1L, ticks - 2), // 2-tick gap avoids NoteOn/NoteOff collision
                            time:   cursor)
                        {
                            Velocity = (SevenBitNumber) 100
                        });
                    }
                    cursor += ticks;
                }
            }
        }

        midiFile.Chunks.Add(tempoTrack);
        midiFile.Chunks.Add(noteTrack);
        return midiFile;
    }

    // Returns (midiNotes, durationTicks) for a single token string.
    private static (List<int> keys, long ticks) ParseToken(string token)
    {
        // Split off optional /N duration suffix
        double divisor = 1;
        var slash = token.IndexOf('/');
        string keyPart;
        if (slash >= 0)
        {
            if (double.TryParse(token[(slash + 1)..], out var d) && d > 0)
                divisor = d;
            keyPart = token[..slash];
        }
        else
        {
            keyPart = token;
        }

        var ticks = (long) Math.Round(Ppq / divisor);
        var keys  = new List<int>();

        if (keyPart == "-")
            return (keys, ticks); // rest — advance time but press nothing

        // Single key or chord: strip optional [ ]
        foreach (var ch in keyPart.TrimStart('[').TrimEnd(']'))
        {
            if (KeyToNote.TryGetValue(char.ToUpper(ch), out var note))
                keys.Add(note);
        }

        return (keys, ticks);
    }
}
