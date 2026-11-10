import localFont from "next/font/local";

// One call per subset file so each gets its own unicode-range (Google Fonts "latin" and
// "cyrillic" plus the Kazakh letters, as split in the Medeo package). Both calls of a family
// declare the same family name and set the same CSS variable to the same value. The fallback-
// metrics face is off: it would be computed from one subset and differ between the calls.
// next/font accepts only inline literals here, so the ranges cannot be shared constants.

const medeoSansLatin = localFont({
  src: "./fonts/MedeoSansVariable.latin.woff2",
  weight: "100 900",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Geist", "Inter", "system-ui", "sans-serif"],
  variable: "--font-medeo-sans",
  declarations: [
    { prop: "font-family", value: "Medeo Sans" },
    {
      prop: "unicode-range",
      value:
        "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
    },
  ],
});

const medeoSansCyrillic = localFont({
  src: "./fonts/MedeoSansVariable.cyrillic.woff2",
  weight: "100 900",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Geist", "Inter", "system-ui", "sans-serif"],
  variable: "--font-medeo-sans",
  declarations: [
    { prop: "font-family", value: "Medeo Sans" },
    {
      prop: "unicode-range",
      value:
        "U+0301, U+0400-045F, U+0490-0493, U+049A-049B, U+04A2-04A3, U+04AE-04B1, U+04BA-04BB, U+04D8-04D9, U+04E8-04E9, U+2116",
    },
  ],
});

const medeoMonoLatin = localFont({
  src: "./fonts/MedeoMonoVariable.latin.woff2",
  weight: "100 900",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Geist Mono", "ui-monospace", "monospace"],
  variable: "--font-medeo-mono",
  declarations: [
    { prop: "font-family", value: "Medeo Mono" },
    {
      prop: "unicode-range",
      value:
        "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
    },
  ],
});

const medeoMonoCyrillic = localFont({
  src: "./fonts/MedeoMonoVariable.cyrillic.woff2",
  weight: "100 900",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Geist Mono", "ui-monospace", "monospace"],
  variable: "--font-medeo-mono",
  declarations: [
    { prop: "font-family", value: "Medeo Mono" },
    {
      prop: "unicode-range",
      value:
        "U+0301, U+0400-045F, U+0490-0493, U+049A-049B, U+04A2-04A3, U+04AE-04B1, U+04BA-04BB, U+04D8-04D9, U+04E8-04E9, U+2116",
    },
  ],
});

export const fontVariables = [medeoSansLatin, medeoSansCyrillic, medeoMonoLatin, medeoMonoCyrillic]
  .map((font) => font.variable)
  .join(" ");
