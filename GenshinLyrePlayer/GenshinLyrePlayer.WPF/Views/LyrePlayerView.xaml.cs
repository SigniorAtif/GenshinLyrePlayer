using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace GenshinLyreMidiPlayer.WPF.Views;

/// <summary>
/// Code-behind for LyrePlayerView — kept minimal.
/// Handles two things that require imperative WPF:
///   1. Auto-scroll the token-stream ListBox when the current token changes.
///   2. Redirect vertical mouse-wheel to horizontal scroll on the token strip.
/// </summary>
public partial class LyrePlayerView : UserControl
{
    public LyrePlayerView()
    {
        InitializeComponent();
    }

    // ── Auto-scroll to current token when selection changes ──────────
    private void TokenStream_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (e.AddedItems.Count > 0)
            TokenStream.ScrollIntoView(e.AddedItems[0]);
    }

    // ── Redirect vertical wheel to horizontal scroll ─────────────────
    private void TokenStream_PreviewMouseWheel(object sender, MouseWheelEventArgs e)
    {
        var sv = FindScrollViewer(TokenStream);
        if (sv is null) return;

        sv.ScrollToHorizontalOffset(sv.HorizontalOffset - e.Delta);
        e.Handled = true;
    }

    private static ScrollViewer? FindScrollViewer(DependencyObject root)
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is ScrollViewer sv) return sv;
            var found = FindScrollViewer(child);
            if (found is not null) return found;
        }
        return null;
    }
}
