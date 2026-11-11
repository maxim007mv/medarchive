import axe from "axe-core";

/** axe violations of impact serious or critical, as readable lines for test diffs. */
export async function seriousViolations(container: Element): Promise<string[]> {
  const { violations } = await axe.run(container, {
    // jsdom does not lay out or paint, so contrast is checked in the browser (brandbook §1.3).
    rules: { "color-contrast": { enabled: false } },
  });
  return violations
    .filter(({ impact }) => impact === "serious" || impact === "critical")
    .map(({ id, nodes }) => `${id}: ${nodes.map((node) => node.target.join(" ")).join(", ")}`);
}
