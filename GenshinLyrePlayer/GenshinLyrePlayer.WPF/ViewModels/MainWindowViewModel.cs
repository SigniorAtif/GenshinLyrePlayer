using System.Windows.Controls;
using GenshinLyreMidiPlayer.Data;
using JetBrains.Annotations;
using Stylet;
using StyletIoC;
using AutoSuggestBox = Wpf.Ui.Controls.AutoSuggestBox;

namespace GenshinLyreMidiPlayer.WPF.ViewModels;

[UsedImplicitly]
public class MainWindowViewModel : Conductor<IScreen>
{
    private readonly IContainer _ioc;

    public MainWindowViewModel(IContainer ioc)
    {
        Title = $"Genshin Lyre Player {SettingsPageViewModel.ProgramVersion}";

        _ioc = ioc;

        PlaylistView   = new(ioc, this);
        SettingsView   = new(ioc, this);
        PianoSheetView = new(this);
        EditorView     = new(ioc.Get<IEventAggregator>());
        ConverterView  = new(this);

        ActiveItem = PlayerView = new(ioc, this);
    }

    public bool ShowUpdate => SettingsView.NeedsUpdate && ActiveItem != SettingsView;

    public string ActiveTab { get; private set; } = "player";

    public LyrePlayerViewModel       PlayerView    { get; }
    public PianoSheetViewModel       PianoSheetView { get; }
    public PlaylistViewModel         PlaylistView  { get; }
    public SettingsPageViewModel     SettingsView  { get; }
    public TokenSheetEditorViewModel EditorView    { get; }
    public ConverterViewModel        ConverterView { get; }
    public string Title { get; set; }

    public void ShowPlayer()
    {
        ActiveTab = "player";
        ActivateItem(PlayerView);
        NotifyOfPropertyChange(() => ShowUpdate);
    }

    public void ShowPlaylist()
    {
        ActiveTab = "playlist";
        ActivateItem(PlaylistView);
    }

    public void ShowSheet()
    {
        ActiveTab = "sheet";
        ActivateItem(PianoSheetView);
    }

    public void ShowEditor()
    {
        ActiveTab = "editor";
        ActivateItem(EditorView);
    }

    public void ShowConverter()
    {
        ActiveTab = "convert";
        ActivateItem(ConverterView);
    }

    public void ShowSettings()
    {
        ActiveTab = "settings";
        ActivateItem(SettingsView);
        NotifyOfPropertyChange(() => ShowUpdate);
    }

    public void NavigateToSettings() => ShowSettings();

    public void SearchSong(AutoSuggestBox sender, TextChangedEventArgs e)
    {
        if (ActiveItem != PlaylistView) ShowPlaylist();
        PlaylistView.FilterText = sender.Text;
    }

    protected override async void OnViewLoaded()
    {
        SettingsView.OnThemeChanged();

        if (!await SettingsView.TryGetLocationAsync()) _ = SettingsView.LocationMissing();
        if (SettingsView.AutoCheckUpdates)
        {
            _ = SettingsView.CheckForUpdate()
                .ContinueWith(_ => { NotifyOfPropertyChange(() => ShowUpdate); });
        }

        await using var db = _ioc.Get<LyreContext>();
        await PlaylistView.AddFiles(db.History);
    }
}
