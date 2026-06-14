using System.Windows.Controls;
using GenshinLyreMidiPlayer.Data;
using JetBrains.Annotations;
using ModernWpf;
using Stylet;
using StyletIoC;
using Wpf.Ui.Appearance;
using Wpf.Ui.Mvvm.Contracts;
using AutoSuggestBox = Wpf.Ui.Controls.AutoSuggestBox;

namespace GenshinLyreMidiPlayer.WPF.ViewModels;

[UsedImplicitly]
public class MainWindowViewModel : Conductor<IScreen>
{
    private readonly IContainer _ioc;
    private readonly IThemeService _theme;

    public MainWindowViewModel(IContainer ioc, IThemeService theme)
    {
        Title = $"Genshin Lyre MIDI Player {SettingsPageViewModel.ProgramVersion}";

        _ioc   = ioc;
        _theme = theme;

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

    public void ToggleTheme()
    {
        ThemeManager.Current.ApplicationTheme = _theme.GetTheme() switch
        {
            ThemeType.Unknown      => ApplicationTheme.Dark,
            ThemeType.Dark         => ApplicationTheme.Light,
            ThemeType.Light        => ApplicationTheme.Dark,
            ThemeType.HighContrast => ApplicationTheme.Dark,
            _                      => ApplicationTheme.Dark
        };

        SettingsView.OnThemeChanged();
    }

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
