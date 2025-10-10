"""
Main entry point for the S3 File Uploader application.

This application combines a GUI file picker with AWS S3 upload functionality.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from file_picker import BasicFileOpenApp
from file_uploader import S3FileUploader

# Load environment variables
load_dotenv()
console = Console()


def print_banner():
    """Display a clean application banner."""
    console.print()
    console.print("=" * 60, style="cyan")
    console.print()
    console.print("  AWS S3 FILE UPLOADER", style="bold bright_white", justify="left")
    console.print("  Cloud storage made simple", style="dim white", justify="left")
    console.print()
    console.print("=" * 60, style="cyan")
    console.print()


def print_section(title):
    """Print a section header."""
    console.print()
    console.print(f"  {title}", style="bold cyan")
    console.print("  " + "-" * 50, style="dim cyan")


def get_aws_config():
    """Get AWS configuration from environment or user input."""
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    region_name = os.getenv("AWS_REGION")

    # Get bucket name if not in environment
    if not bucket_name:
        print_section("Configuration Required")
        console.print("  [yellow]AWS_S3_BUCKET_NAME not set in environment[/yellow]")
        console.print()
        bucket_name = Prompt.ask("  Bucket Name")

        if not bucket_name:
            console.print()
            console.print("  [red]Error:[/red] Bucket name is required", style="")
            console.print()
            sys.exit(1)

    # Get region if not in environment
    if not region_name:
        region_name = Prompt.ask("  AWS Region", default="eu-central-1")

    # Display configuration
    print_section("Configuration")

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Key", style="dim")
    table.add_column("Value", style="bright_white")

    table.add_row("Bucket", bucket_name)
    table.add_row("Region", region_name)

    console.print(table)
    console.print()

    return bucket_name, region_name


def create_uploader(bucket_name, region_name):
    """Create and verify S3 uploader connection."""
    console.print("  Connecting to S3...", style="dim")

    uploader = S3FileUploader(
        bucket_name=bucket_name,
        region_name=region_name,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    # Verify bucket access
    if not uploader.bucket_exists():
        console.print()
        console.print("  [red]Connection Failed[/red]")
        console.print()
        console.print("  Cannot access S3 bucket. Please verify:")
        console.print("    - Bucket name is correct")
        console.print("    - AWS credentials are configured")
        console.print("    - You have proper permissions")
        console.print()
        sys.exit(1)

    console.print("  [green]Connected successfully[/green]")
    return uploader


def list_bucket_contents(uploader):
    """List and display bucket contents."""
    prefix = Prompt.ask("  Filter by prefix", default="")
    console.print()
    uploader.list_bucket_contents(prefix=prefix)


def upload_single_file(uploader):
    """Handle single file upload workflow."""
    console.print()
    console.print("  Opening file picker...", style="dim")

    try:
        file_path = BasicFileOpenApp().run()

        if file_path is None:
            console.print()
            console.print("  [yellow]File selection cancelled[/yellow]")
            return

        file_path = Path(file_path)
        console.print(f"  Selected: [dim]{file_path}[/dim]")
        console.print()

        # Get S3 key
        use_custom_key = Confirm.ask(
            "  Customize S3 path? (default: media/filename)", default=False
        )

        if use_custom_key:
            s3_key = Prompt.ask("  S3 Key", default=f"media/{file_path.name}")
        else:
            s3_key = f"media/{file_path.name}"

        console.print()
        console.print(f"  Uploading to: [cyan]{s3_key}[/cyan]")

        # Upload
        success = uploader.upload_file(file_path, s3_key=s3_key)

        console.print()
        if success:
            console.print("  [green]Upload completed successfully[/green]")
        else:
            console.print("  [red]Upload failed[/red]")
            console.print("  Check the errors above for details")

    except Exception as e:
        console.print()
        console.print(f"  [red]Error:[/red] {e}")


def upload_directory(uploader):
    """Handle directory upload workflow."""
    dir_path = Prompt.ask("  Directory path")
    dir_path = Path(dir_path)

    if not dir_path.exists() or not dir_path.is_dir():
        console.print()
        console.print(f"  [red]Error:[/red] Directory not found: {dir_path}")
        return

    s3_prefix = Prompt.ask("  S3 prefix (folder path in bucket)", default="")

    # File filters
    console.print()
    use_filters = Confirm.ask("  Apply file filters?", default=False)

    include_patterns = None
    exclude_patterns = None

    if use_filters:
        include_str = Prompt.ask("  Include patterns (e.g., *.txt,*.pdf)", default="")
        if include_str:
            include_patterns = [p.strip() for p in include_str.split(",")]

        exclude_str = Prompt.ask("  Exclude patterns (e.g., *.tmp,*.log)", default="")
        if exclude_str:
            exclude_patterns = [p.strip() for p in exclude_str.split(",")]

    console.print()
    console.print("  Uploading directory contents...", style="dim")

    # Upload
    successful, failed = uploader.upload_directory(
        dir_path,
        s3_prefix=s3_prefix,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )

    # Results
    console.print()
    if failed == 0:
        console.print(
            f"  [green]All files uploaded successfully[/green] ({successful} files)"
        )
    else:
        console.print(f"  [yellow]Upload completed with issues[/yellow]")
        console.print(f"  Successful: {successful}")
        console.print(f"  Failed: {failed}")


def show_menu():
    """Display main menu and get user choice."""
    print_section("Main Menu")

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Command", style="bold cyan")
    table.add_column("Description", style="bright_white")

    table.add_row("upload", "Upload file or directory")
    table.add_row("list", "List bucket contents")
    table.add_row("exit", "Exit application")

    console.print(table)
    console.print()

    action = Prompt.ask(
        "  Choose an action", choices=["upload", "list", "exit"], default="upload"
    )

    return action


def main():
    """Main application entry point."""
    # Display banner
    print_banner()

    # Get configuration
    bucket_name, region_name = get_aws_config()

    # Create and verify uploader
    uploader = create_uploader(bucket_name, region_name)

    # Main loop
    while True:
        action = show_menu()

        if action == "exit":
            console.print()
            console.print("  Goodbye!", style="cyan")
            console.print()
            break

        elif action == "list":
            console.print()
            list_bucket_contents(uploader)
            console.print()
            input("  Press Enter to continue...")
            console.clear()
            print_banner()

        elif action == "upload":
            console.print()
            upload_type = Prompt.ask(
                "  What to upload?", choices=["file", "directory"], default="file"
            )

            if upload_type == "file":
                upload_single_file(uploader)
            else:
                upload_directory(uploader)

            console.print()

            # Ask if user wants to continue
            if not Confirm.ask("  Perform another operation?", default=True):
                console.print()
                console.print("  Goodbye!", style="cyan")
                console.print()
                break

            console.clear()
            print_banner()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n")
        console.print("  Operation cancelled", style="yellow")
        console.print()
        sys.exit(0)
    except Exception as e:
        console.print("\n")
        console.print(f"  [red]Error:[/red] {e}")
        console.print()
        sys.exit(1)
