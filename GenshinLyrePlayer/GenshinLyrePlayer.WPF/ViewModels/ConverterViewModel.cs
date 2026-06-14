using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using JetBrains.Annotations;
using Microsoft.Win32;
using Stylet;

namespace GenshinLyreMidiPlayer.WPF.ViewModels;

[UsedImplicitly]
public class ConverterViewModel : Screen
{
    private readonly MainWindowViewModel _main;
    private CancellationTokenSource? _cts;

    public ConverterViewModel(MainWindowViewModel main)
    {
        _main = main;
    }

    // ── Input ────────────────────────────────────────────────────────
    public string VideoPath  { get; set; } = "";
    public string OutputPath { get; set; } = "";
    public string BpmText    { get; set; } = "";
    public bool   DebugMode  { get; set; }

    // ── State ────────────────────────────────────────────────────────
    public bool   IsConverting    { get; private set; }
    public bool   ConvertDone     { get; private set; }
    public bool   ConvertSuccess  { get; private set; }
    public double ProgressValue   { get; private set; }
    public bool   IsIndeterminate { get; private set; } = true;
    public string LogOutput       { get; private set; } = "";
    public string StatusMessage   { get; private set; } = "";

    public bool CanConvert =>
        !string.IsNullOrWhiteSpace(VideoPath) &&
        File.Exists(VideoPath)                &&
        !IsConverting;

    /// <summary>True while converting or after it finishes — reveals the log + progress panel.</summary>
    public bool ShowLog    => IsConverting || ConvertDone;
    public bool ShowResult => ConvertDone  && ConvertSuccess;

    // ── Commands ─────────────────────────────────────────────────────
    public void BrowseVideo()
    {
        var dlg = new OpenFileDialog
        {
            Filter = "Video files|*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.m4v|All files|*.*",
            Title  = "Select gameplay video"
        };
        if (dlg.ShowDialog() != true) return;

        VideoPath = dlg.FileName;

        // Auto-fill output path when the user hasn't entered one yet
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            var dir  = Path.GetDirectoryName(dlg.FileName) ?? "";
            var name = Path.GetFileNameWithoutExtension(dlg.FileName) + ".txt";
            OutputPath = Path.Combine(dir, name);
        }

        NotifyOfPropertyChange(nameof(CanConvert));
    }

    public void BrowseOutput()
    {
        var dlg = new SaveFileDialog
        {
            Filter     = "Token Sheet (*.txt)|*.txt|All files|*.*",
            Title      = "Save output token sheet",
            DefaultExt = ".txt",
            FileName   = OutputPath
        };
        if (dlg.ShowDialog() != true) return;
        OutputPath = dlg.FileName;
    }

    // Called by Fody when VideoPath changes
    public void OnVideoPathChanged() => NotifyOfPropertyChange(nameof(CanConvert));

    public async Task Convert()
    {
        if (!CanConvert) return;

        IsConverting    = true;
        ConvertDone     = false;
        ConvertSuccess  = false;
        ProgressValue   = 0;
        IsIndeterminate = true;
        LogOutput       = "";
        StatusMessage   = "Starting…";
        NotifyOfPropertyChange(nameof(CanConvert));
        NotifyOfPropertyChange(nameof(ShowLog));
        NotifyOfPropertyChange(nameof(ShowResult));

        var cmd = BuildCommand();
        if (cmd is null)
        {
            AppendLog("ERROR: Could not find 'genshin-parse' or Python.");
            AppendLog("");
            AppendLog("To fix this, do one of the following:");
            AppendLog("  Option A: Install the package — open a terminal in the");
            AppendLog("            GenshinMusic folder and run: pip install -e .");
            AppendLog("  Option B: Ensure 'python' is on your PATH and this app");
            AppendLog("            is running from inside the GenshinMusic repo.");
            IsConverting   = false;
            ConvertDone    = true;
            ConvertSuccess = false;
            StatusMessage  = "Setup error — Python / genshin-parse not found";
            NotifyOfPropertyChange(nameof(CanConvert));
            NotifyOfPropertyChange(nameof(ShowLog));
            NotifyOfPropertyChange(nameof(ShowResult));
            return;
        }

        _cts = new CancellationTokenSource();
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName               = cmd.Value.Exe,
                Arguments              = cmd.Value.Args,
                WorkingDirectory       = cmd.Value.WorkDir ?? "",
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
                CreateNoWindow         = true,
            };

            AppendLog($"> {cmd.Value.Exe} {cmd.Value.Args}");
            AppendLog("");

            using var process = new Process { StartInfo = psi, EnableRaisingEvents = true };
            process.OutputDataReceived += (_, e) => ParseProgress(e.Data);
            process.ErrorDataReceived  += (_, e) => AppendLog(e.Data);

            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            await process.WaitForExitAsync(_cts.Token);

            ConvertSuccess = process.ExitCode == 0;
            if (ConvertSuccess)
            {
                ProgressValue   = 100;
                IsIndeterminate = false;
                StatusMessage   = $"Done!  →  {Path.GetFileName(OutputPath)}";
            }
            else
            {
                StatusMessage = $"Conversion failed (exit code {process.ExitCode})";
            }
        }
        catch (OperationCanceledException)
        {
            AppendLog("\n[Cancelled by user]");
            StatusMessage  = "Cancelled";
            ConvertSuccess = false;
        }
        catch (Exception ex)
        {
            AppendLog($"\nERROR: {ex.Message}");
            StatusMessage  = "Error during conversion";
            ConvertSuccess = false;
        }
        finally
        {
            IsConverting = false;
            ConvertDone  = true;
            NotifyOfPropertyChange(nameof(CanConvert));
            NotifyOfPropertyChange(nameof(ShowLog));
            NotifyOfPropertyChange(nameof(ShowResult));
        }
    }

    public void Cancel() => _cts?.Cancel();

    public async Task AddToPlaylist()
    {
        if (!File.Exists(OutputPath)) return;
        _main.ShowPlaylist();
        await _main.PlaylistView.AddFiles(new[] { OutputPath });
    }

    public async Task OpenInEditor()
    {
        _main.ShowEditor();
        await _main.EditorView.LoadFile(OutputPath);
    }

    public void Reset()
    {
        ConvertDone     = false;
        ConvertSuccess  = false;
        ProgressValue   = 0;
        IsIndeterminate = true;
        LogOutput       = "";
        StatusMessage   = "";
        _cts            = null;
        NotifyOfPropertyChange(nameof(ShowLog));
        NotifyOfPropertyChange(nameof(ShowResult));
    }

    // ── Helpers ──────────────────────────────────────────────────────

    private void AppendLog(string? line)
    {
        if (line is null) return;
        Application.Current.Dispatcher.BeginInvoke(() => LogOutput += line + "\n");
    }

    private void ParseProgress(string? line)
    {
        if (line is null || !line.StartsWith("PROGRESS ", StringComparison.Ordinal)) return;

        var parts = line[9..].Split('/');
        if (parts.Length != 2) return;
        if (!int.TryParse(parts[0], out var cur) || !int.TryParse(parts[1], out var total)) return;
        if (total <= 0) return;

        Application.Current.Dispatcher.BeginInvoke(() =>
        {
            IsIndeterminate = false;
            ProgressValue   = (double)cur / total * 100.0;
        });
    }

    private (string Exe, string Args, string? WorkDir)? BuildCommand()
    {
        if (string.IsNullOrWhiteSpace(VideoPath) || string.IsNullOrWhiteSpace(OutputPath)) return null;

        var sb = new StringBuilder();
        sb.Append($"--video \"{VideoPath}\" --output \"{OutputPath}\" --progress-stdout");

        var bpmStr = BpmText?.Trim() ?? "";
        if (!string.IsNullOrEmpty(bpmStr) &&
            double.TryParse(bpmStr, NumberStyles.Any, CultureInfo.InvariantCulture, out var bpm) &&
            bpm > 0)
        {
            sb.Append($" --bpm {bpm.ToString(CultureInfo.InvariantCulture)}");
        }

        if (DebugMode) sb.Append(" --debug");
        var extraArgs = sb.ToString();

        // ── Option 0: genshin-parse.exe bundled next to this app (release build) ──
        // This is checked first so the release layout always wins.
        var bundledExe = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "genshin-parse.exe");
        if (File.Exists(bundledExe))
            return (bundledExe, extraArgs, null);

        // ── Option 1: genshin-parse on PATH (pip install -e . users) ──
        if (TryFindExe("genshin-parse"))
            return ("genshin-parse", extraArgs, null);

        // ── Option 2: python -m (dev — app is running from inside the repo) ──
        var root = FindPythonProjectRoot();
        if (root is not null)
        {
            if (TryFindExe("python"))
                return ("python", $"-m vision_parser.parser_pipeline {extraArgs}", root);
            if (TryFindExe("python3"))
                return ("python3", $"-m vision_parser.parser_pipeline {extraArgs}", root);
        }

        return null;
    }

    /// <summary>Returns true if <paramref name="name"/> can be resolved via 'where' on Windows PATH.</summary>
    private static bool TryFindExe(string name)
    {
        try
        {
            var psi = new ProcessStartInfo("where", name)
            {
                RedirectStandardOutput = true,
                UseShellExecute        = false,
                CreateNoWindow         = true,
            };
            using var p = Process.Start(psi);
            if (p is null) return false;
            var found = p.StandardOutput.ReadLine();
            p.WaitForExit();
            return p.ExitCode == 0 && !string.IsNullOrWhiteSpace(found);
        }
        catch { return false; }
    }

    /// <summary>
    /// Walk up from the app's base directory until we find a folder that contains
    /// a <c>vision_parser/</c> sub-directory — that is the Python project root.
    /// </summary>
    private static string? FindPythonProjectRoot()
    {
        var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
        while (dir is not null)
        {
            if (Directory.Exists(Path.Combine(dir.FullName, "vision_parser")))
                return dir.FullName;
            dir = dir.Parent;
        }
        return null;
    }
}
