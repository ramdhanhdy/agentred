"""AgentRed CLI: command-line interface for the MapReduce demand intelligence pipeline."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from agentred.orchestrator import collect_all, run_mapreduce, save_run_report
from agentred.report import generate_markdown, generate_docx
from agentred.schemas import RunReport

console = Console()


def make_llm_call(provider: str, model: str):
    """Create an LLM call function using the OpenAI-compatible API.

    Supports:
    - opencode-go: OpenRouter-style gateway (default)
    - openrouter: direct OpenRouter
    - deepseek: DeepSeek API
    - zai: Z.AI/GLM API
    - longcat: LongCat API
    """

    # Determine API key and base URL based on provider
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        base_url = "https://openrouter.ai/api/v1"
    elif provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = "https://api.deepseek.com/v1"
    elif provider == "zai":
        api_key = os.environ.get("GLM_API_KEY", "")
        base_url = "https://api.z.ai/api/paas/v4"
    elif provider == "longcat":
        api_key = os.environ.get("LONGCAT_API_KEY", "")
        base_url = "https://api.longcat.chat/openai"
    else:  # opencode-go (default)
        api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
        base_url = "https://opencode.ai/zen/go/v1"

    if not api_key:
        raise ValueError(f"No API key found for provider '{provider}'")

    import urllib.request

    def llm_call(system_prompt: str, user_prompt: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 8000,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]

    return llm_call


@click.group()
@click.version_option(package_name="agentred")
def main():
    """AgentRed - Agentic Reduce for job market demand intelligence."""
    pass


@main.command()
@click.option("--provider", default="opencode-go", help="LLM provider")
@click.option("--model", required=True, help="LLM model name")
@click.option("--output", "-o", default="output", help="Output directory")
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "docx", "both"]))
@click.option("--no-exa", is_flag=True, help="Skip EXA (Upwork/Fiverr)")
@click.option("--no-himalayas", is_flag=True, help="Skip Himalayas")
@click.option("--no-jobicy", is_flag=True, help="Skip Jobicy")
@click.option("--batch-size", type=int, default=None, help="Override batch size")
def run(provider, model, output, fmt, no_exa, no_himalayas, no_jobicy, batch_size):
    """Run the full MapReduce pipeline: collect, map, reduce, report."""

    console.print("[bold red]AgentRed[/bold red] - Agentic Reduce")
    console.print(f"Provider: {provider} | Model: {model}")
    console.print()

    # Phase 1: Collect
    console.print("[bold]Phase 1: Collection[/bold]")
    posts = collect_all(
        use_exa=not no_exa,
        use_himalayas=not no_himalayas,
        use_jobicy=not no_jobicy,
    )
    console.print(f"  Collected {len(posts)} unique job posts")
    console.print()

    if not posts:
        console.print("[red]No posts collected. Check API keys and connectivity.[/red]")
        sys.exit(1)

    # Phase 2-3: MapReduce
    console.print("[bold]Phase 2: MapReduce[/bold]")
    llm_call = make_llm_call(provider, model)

    def progress(phase: str, current: int, total: int):
        if phase == "map":
            console.print(f"  [Map] Batch {current}/{total}")
        elif phase == "reduce":
            console.print(f"  [Reduce] {'done' if current else 'starting...'}")

    map_results, report = run_mapreduce(
        posts, llm_call, batch_size=batch_size, progress_callback=progress
    )

    console.print()
    console.print(f"  Signals extracted: {sum(len(r.demand_signals) for r in map_results)}")
    console.print(f"  Opportunities: {len(report.reduce_result.opportunities) if report.reduce_result else 0}")
    console.print(f"  Wall clock: {report.wall_clock_seconds:.1f}s")
    console.print()

    # Phase 4: Report
    console.print("[bold]Phase 3: Report Generation[/bold]")
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = save_run_report(report, output)
    console.print(f"  JSON: {json_path}")

    # Save markdown
    if fmt in ("markdown", "both"):
        md = generate_markdown(report)
        md_path = out_dir / f"{report.run_id}.md"
        md_path.write_text(md)
        console.print(f"  Markdown: {md_path}")

    # Save DOCX
    if fmt in ("docx", "both"):
        try:
            docx_path = generate_docx(report, out_dir / f"{report.run_id}.docx")
            console.print(f"  DOCX: {docx_path}")
        except ImportError as e:
            console.print(f"  [yellow]DOCX skipped: {e}[/yellow]")

    console.print()
    console.print("[bold green]Done.[/bold green]")

    # Print top opportunities
    if report.reduce_result and report.reduce_result.opportunities:
        table = Table(title="Top Opportunities")
        table.add_column("#", style="dim")
        table.add_column("Opportunity", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Competition")

        for opp in report.reduce_result.opportunities[:10]:
            table.add_row(
                str(opp.rank),
                opp.title[:60],
                f"{opp.demand_score:.0f}",
                opp.competition_level,
            )
        console.print(table)


@main.command()
@click.option("--output", "-o", default="output", help="Output directory")
@click.option("--no-exa", is_flag=True, help="Skip EXA (Upwork/Fiverr)")
@click.option("--no-himalayas", is_flag=True, help="Skip Himalayas")
@click.option("--no-jobicy", is_flag=True, help="Skip Jobicy")
def collect(output, no_exa, no_himalayas, no_jobicy):
    """Collect job posts only (no LLM analysis). Saves as JSON."""

    console.print("[bold red]AgentRed[/bold red] - Collection Only")
    console.print()

    posts = collect_all(
        use_exa=not no_exa,
        use_himalayas=not no_himalayas,
        use_jobicy=not no_jobicy,
    )

    console.print(f"\nCollected {len(posts)} unique job posts")

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dt%H%M%SZ")
    path = out_dir / f"collected-{ts}.json"

    path.write_text(
        json.dumps([p.model_dump(mode="json") for p in posts], indent=2)
    )
    console.print(f"Saved to: {path}")


if __name__ == "__main__":
    main()
