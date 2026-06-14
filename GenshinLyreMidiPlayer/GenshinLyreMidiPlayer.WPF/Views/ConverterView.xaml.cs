using System.Windows.Controls;

namespace GenshinLyreMidiPlayer.WPF.Views;

public partial class ConverterView : UserControl
{
    public ConverterView() { InitializeComponent(); }

    /// <summary>Auto-scroll the log TextBox to the bottom as new lines arrive.</summary>
    private void LogBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        LogBox.ScrollToEnd();
    }
}
