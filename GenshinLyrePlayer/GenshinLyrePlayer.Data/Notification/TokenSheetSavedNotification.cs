namespace GenshinLyreMidiPlayer.Data.Notification;

/// <summary>
/// Published by <c>TokenSheetEditorViewModel</c> after a .txt file is saved.
/// <c>PlaylistViewModel</c> handles this to refresh any playlist entry whose
/// path matches, so the duration label updates without reopening the file.
/// </summary>
public record TokenSheetSavedNotification(string Path);
