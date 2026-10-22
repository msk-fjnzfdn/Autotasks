import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 20, color: "#f58a8a" }}>
          <h2>Что-то сломалось на странице</h2>
          <pre>{String(this.state.error)}</pre>
          <button onClick={() => this.setState({ error: null })}>Попробовать снова</button>
        </div>
      );
    }
    return this.props.children;
  }
}
