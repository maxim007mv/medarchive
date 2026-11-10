// Local ESLint rules for TZ-frontend §0 and §5: colours, sizes and spacing come only from tokens.
// eslint-plugin-tailwindcss does not understand Tailwind 4, so the checks are written here.

const HEX_COLOR = /#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})(?![0-9a-z])/i;
// Names whose value holds Tailwind classes besides `className` and `cn(...)` arguments.
const CLASS_HOLDER = /class(?:es|name)?$/i;
const SPACING_UTILITY =
  /^-?(?:p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy]|scroll-[mp][xytrblse]?)-(.+)$/;
// tokens.json `space`: 8/16/24/32/48(/64) for layout, 2/4/6/10/12(/20) inside components.
const SPACING_STEPS = new Set([
  "0",
  "0.5",
  "1",
  "1.5",
  "2",
  "2.5",
  "3",
  "4",
  "5",
  "6",
  "8",
  "12",
  "16",
]);
const SPACING_KEYWORDS = new Set(["auto", "safe", "reverse"]);

function stringValue(node) {
  if (node.type === "Literal" && typeof node.value === "string") return node.value;
  if (node.type === "TemplateElement") return node.value.cooked ?? node.value.raw;
  return null;
}

function nameOf(node) {
  if (!node) return "";
  if (node.type === "Identifier" || node.type === "JSXIdentifier") return node.name;
  if (node.type === "Literal") return String(node.value);
  return "";
}

function isClassContext(ancestor) {
  switch (ancestor.type) {
    case "JSXAttribute":
      return nameOf(ancestor.name) === "className";
    case "CallExpression":
      return nameOf(ancestor.callee) === "cn";
    case "VariableDeclarator":
      return CLASS_HOLDER.test(nameOf(ancestor.id));
    case "Property":
      return CLASS_HOLDER.test(nameOf(ancestor.key));
    default:
      return false;
  }
}

/** The utility part of a class: variants such as `md:` or `data-[state=open]:` stripped. */
function utilityOf(token) {
  let depth = 0;
  let start = 0;
  for (let i = 0; i < token.length; i += 1) {
    const char = token[i];
    if (char === "[" || char === "(") depth += 1;
    else if (char === "]" || char === ")") depth -= 1;
    else if (char === ":" && depth === 0) start = i + 1;
  }
  return token.slice(start).replace(/^!|!$/g, "");
}

function classProblem(token) {
  const utility = utilityOf(token);
  if (/[[(]/.test(utility)) return { messageId: "arbitrary", data: { token } };
  const spacing = SPACING_UTILITY.exec(utility);
  if (spacing && !SPACING_STEPS.has(spacing[1]) && !SPACING_KEYWORDS.has(spacing[1])) {
    return { messageId: "spacing", data: { token } };
  }
  return null;
}

const noHexColor = {
  meta: {
    type: "problem",
    docs: { description: "Forbid raw hex colours; use token utilities or variables." },
    messages: { hex: "Raw colour {{color}}: use a token (bg-surface, var(--c-text) …)." },
    schema: [],
  },
  create(context) {
    function check(node) {
      const color = HEX_COLOR.exec(stringValue(node) ?? "")?.[0];
      if (color) context.report({ node, messageId: "hex", data: { color } });
    }
    return { Literal: check, TemplateElement: check };
  },
};

const tailwindTokens = {
  meta: {
    type: "problem",
    docs: { description: "Forbid arbitrary Tailwind values and spacing outside the token scale." },
    messages: {
      arbitrary: "Arbitrary value in «{{token}}»: add a token to styles/theme.css instead.",
      spacing: "«{{token}}» is off the spacing scale (2/4/6/10/12 inside, 8/16/24/32/48 layout).",
    },
    schema: [],
  },
  create(context) {
    function check(node) {
      const value = stringValue(node);
      if (!value) return;
      if (!context.sourceCode.getAncestors(node).some(isClassContext)) return;
      for (const token of value.split(/\s+/).filter(Boolean)) {
        const problem = classProblem(token);
        if (problem) context.report({ node, ...problem });
      }
    }
    return { Literal: check, TemplateElement: check };
  },
};

const designTokens = {
  meta: { name: "design-tokens" },
  rules: { "no-hex-color": noHexColor, "tailwind-tokens": tailwindTokens },
};

export default designTokens;
