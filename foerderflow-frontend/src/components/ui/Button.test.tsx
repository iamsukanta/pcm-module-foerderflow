import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/**
 * Placeholder smoke test proving the component test harness works.
 * Real component tests land in Phase 4 as components/ui is ported.
 */
function Placeholder() {
  return <button type="button">Speichern</button>;
}

describe("test harness", () => {
  it("renders", () => {
    render(<Placeholder />);
    expect(screen.getByRole("button", { name: "Speichern" })).toBeInTheDocument();
  });
});
