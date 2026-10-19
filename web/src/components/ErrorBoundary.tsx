import { Component, type ComponentChildren } from "preact";

export class ErrorBoundary extends Component<{ children: ComponentChildren; page: string }, { failed: boolean }> {
  override state = { failed: false };

  static override getDerivedStateFromError() {
    return { failed: true };
  }

  override componentDidCatch(error: unknown) {
    console.error("Page failed to render:", error);
  }

  override componentDidUpdate(previous: { page: string }) {
    if (previous.page !== this.props.page && this.state.failed) this.setState({ failed: false });
  }

  override render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div class="container narrow center not-found" role="alert">
        <h1>Something went wrong on this page</h1>
        <p class="section-lede">Reloading usually fixes it. Your loaded repositories stay cached in this browser.</p>
        <div class="case-links">
          <button class="btn primary" type="button" onClick={() => location.reload()}>Reload the page</button>
        </div>
      </div>
    );
  }
}
