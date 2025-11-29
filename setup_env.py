import os
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

# Load environment
load_dotenv()

# Initialize Rich Console
console = Console()

REQUIRED_KEYS = [
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
    "OPENAI_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY"
]

def check_env_vars():
    # Create a stylized table
    table = Table(title="Environment Variable Check", box=box.ROUNDED, show_lines=True)
    
    table.add_column("Variable Name", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Details", style="magenta")

    all_passed = True

    for key in REQUIRED_KEYS:
        value = os.getenv(key)
        
        if not value:
            table.add_row(key, "[red]❌ MISSING[/red]", "-")
            all_passed = False
        elif value.startswith("<") or value.endswith(">"):
            table.add_row(key, "[yellow]⚠️  PLACEHOLDER[/yellow]", f"Length: {len(value)}")
            all_passed = False
        else:
            table.add_row(key, "[green]✅ SET[/green]", f"Length: {len(value)}")

    console.print(table)
    
    if not all_passed:
        console.print("\n[bold red]Action Required:[/bold red] Please check your .env file.")

if __name__ == "__main__":
    check_env_vars()