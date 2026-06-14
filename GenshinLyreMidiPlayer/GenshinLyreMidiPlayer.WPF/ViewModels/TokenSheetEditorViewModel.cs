using System.Collections.ObjectModel;
using System.IO;
using System.Threading.Tasks;
using GenshinLyreMidiPlayer.Data.Notification;
using JetBrains.Annotations;
using Microsoft.Win32;
using Stylet;

namespace GenshinLyreMidiPlayer.WPF.ViewModels;

[UsedImplicitly]
public class TokenSheetEditorViewModel : Screen
{
    private readonly IEventAggregator _events;
    private string? _filePath;
    private bool _suppressLoad;

    public TokenSheetEditorViewModel(IEventAggregator events)
    {
        _events = events;
    }

    public string Content { get; set; } = "BPM 120\n\n";
    public string FileName { get; set; } = "Untitled.txt";
    public bool HasChanges { get; private set; }

    // ── File browser sidebar ─────────────────────────────
    public string? SheetDirectory { get; private set; }
    public string? SelectedSheetFile { get; set; }
    public ObservableCollection<string> SheetFileNames { get; } = new();

    /// Called by PropertyChanged.Fody when SelectedSheetFile changes.
    public async void OnSelectedSheetFileChanged()
    {
        if (_suppressLoad) return;
        if (string.IsNullOrEmpty(SelectedSheetFile) || SheetDirectory is null) return;

        var path = Path.Combine(SheetDirectory, SelectedSheetFile);
        if (!File.Exists(path)) return;

        await LoadFileFromPath(path);
    }

    public void BrowseDirectory()
    {
        // Use an OpenFileDialog so the user navigates to the folder they want.
        // Whichever .txt file they open sets the watched directory.
        var dialog = new OpenFileDialog
        {
            Filter = "Token Sheet (*.txt)|*.txt|All Files (*.*)|*.*",
            Title  = "Open any file to set folder"
        };
        if (dialog.ShowDialog() != true) return;

        var dir = Path.GetDirectoryName(dialog.FileName);
        if (dir is null) return;

        SetDirectory(dir);

        // Sync list selection without re-loading (we'll load below)
        _suppressLoad = true;
        SelectedSheetFile = Path.GetFileName(dialog.FileName);
        _suppressLoad = false;

        // Load the file the user picked
        _ = LoadFileFromPath(dialog.FileName);
    }

    public void RefreshFiles() => SetDirectory(SheetDirectory);

    // ── External entry point (e.g. from ConverterViewModel) ─
    public async Task LoadFile(string path) => await LoadFileFromPath(path);

    // ── Direct open / save ───────────────────────────────
    public async Task OpenFile()
    {
        var dialog = new OpenFileDialog
        {
            Filter = "Token Sheet (*.txt)|*.txt|All Files (*.*)|*.*",
            Title  = "Open Token Sheet"
        };
        if (dialog.ShowDialog() != true) return;

        await LoadFileFromPath(dialog.FileName);

        // Populate the sidebar from the opened file's directory
        var dir = Path.GetDirectoryName(dialog.FileName);
        if (dir is not null && dir != SheetDirectory) SetDirectory(dir);

        _suppressLoad = true;
        SelectedSheetFile = Path.GetFileName(dialog.FileName);
        _suppressLoad = false;
    }

    public async Task SaveFile()
    {
        if (_filePath is null) { await SaveFileAs(); return; }
        await File.WriteAllTextAsync(_filePath, Content);
        HasChanges = false;
        _events.Publish(new TokenSheetSavedNotification(_filePath));
    }

    public async Task SaveFileAs()
    {
        var dialog = new SaveFileDialog
        {
            Filter     = "Token Sheet (*.txt)|*.txt|All Files (*.*)|*.*",
            Title      = "Save Token Sheet",
            FileName   = FileName,
            DefaultExt = ".txt"
        };
        if (dialog.ShowDialog() != true) return;

        _filePath  = dialog.FileName;
        FileName   = Path.GetFileName(dialog.FileName);
        await File.WriteAllTextAsync(_filePath, Content);
        HasChanges = false;
        _events.Publish(new TokenSheetSavedNotification(_filePath));

        // Refresh sidebar in case saved to a new location
        var dir = Path.GetDirectoryName(dialog.FileName);
        if (dir is not null) SetDirectory(dir);
    }

    // ── Helpers ──────────────────────────────────────────
    private async Task LoadFileFromPath(string path)
    {
        _filePath  = path;
        FileName   = Path.GetFileName(path);
        Content    = await File.ReadAllTextAsync(path);
        HasChanges = false;
    }

    private void SetDirectory(string? dir)
    {
        if (dir is null || !Directory.Exists(dir)) return;
        SheetDirectory = dir;
        SheetFileNames.Clear();
        foreach (var f in Directory.GetFiles(dir, "*.txt"))
            SheetFileNames.Add(Path.GetFileName(f));
    }
}
