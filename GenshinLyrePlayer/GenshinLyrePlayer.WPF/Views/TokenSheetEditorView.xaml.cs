using System.Windows;
using System.Windows.Controls;

namespace GenshinLyreMidiPlayer.WPF.Views;

public partial class TokenSheetEditorView : UserControl
{
    public TokenSheetEditorView()
    {
        InitializeComponent();
    }

    private void OnKeyButtonClick(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string key }) return;

        var pos = EditorTextBox.SelectionStart;
        var text = EditorTextBox.Text;

        var needsSpace = pos > 0 && text[pos - 1] is not ('\n' or ' ');
        var token = needsSpace ? " " + key : key;

        EditorTextBox.Text = text.Insert(pos, token);
        EditorTextBox.SelectionStart = pos + token.Length;
        EditorTextBox.Focus();
    }
}
