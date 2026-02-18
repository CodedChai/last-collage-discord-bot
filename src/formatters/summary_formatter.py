from urllib.parse import quote_plus

from services.summary_service import GroupSummary


def format_summary_text(summary: GroupSummary) -> str:
    lines: list[str] = []

    lines.append("**Weekly Group Summary**\n")

    if summary.most_overlapping:
        o = summary.most_overlapping
        parts = []
        if o.shared_artists:
            parts.append(f"{len(o.shared_artists)} artist{'s' if len(o.shared_artists) != 1 else ''}")
        if o.shared_albums:
            parts.append(f"{len(o.shared_albums)} album{'s' if len(o.shared_albums) != 1 else ''}")
        if o.shared_tracks:
            parts.append(f"{len(o.shared_tracks)} track{'s' if len(o.shared_tracks) != 1 else ''}")
        shared_detail = ", ".join(parts)
        lines.append(
            f"🎵 **{o.user_a}** and **{o.user_b}** have the most in common "
            f"({shared_detail})!"
        )
    else:
        lines.append("🎵 Everyone has pretty unique taste — no overlap found!")

    if summary.biggest_outlier:
        lines.append(
            f"🦄 **{summary.biggest_outlier}** is the biggest outlier of the group."
        )

    if summary.popular_artists:
        lines.append("\n🏆 **Group Favorite Artists:**")
        for name, user_list in summary.popular_artists[:5]:
            users_str = ", ".join(user_list)
            lines.append(f"• {name} ({users_str})")

    if summary.popular_albums:
        lines.append("\n💿 **Group Favorite Albums:**")
        for name, user_list in summary.popular_albums[:5]:
            users_str = ", ".join(user_list)
            lines.append(f"• {name} ({users_str})")

    if summary.popular_tracks:
        lines.append("\n🎶 **Group Favorite Tracks:**")
        for name, user_list in summary.popular_tracks[:5]:
            users_str = ", ".join(user_list)
            youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(name.replace(' - ', ' '))}"
            lines.append(f"• [{name}](<{youtube_url}>) ({users_str})")

    if summary.hidden_gem:
        user, track_name, playcount = summary.hidden_gem
        youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(track_name.replace(' - ', ' '))}"
        lines.append(
            f"\n💎 **Hidden Gem:**\n"
            f"**{user}** has [{track_name}](<{youtube_url}>) on repeat ({playcount} plays)!"
        )

    lines.append(f"\n---\n*{summary.user_count} participants this week*")

    return "\n".join(lines)
