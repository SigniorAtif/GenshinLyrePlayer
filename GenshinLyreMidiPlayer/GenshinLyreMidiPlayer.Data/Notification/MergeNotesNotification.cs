namespace GenshinLyreMidiPlayer.Data.Notification;

public class MergeNotesNotification
{
    public MergeNotesNotification(bool merge) { Merge = merge; }

    public bool Merge { get; }
}