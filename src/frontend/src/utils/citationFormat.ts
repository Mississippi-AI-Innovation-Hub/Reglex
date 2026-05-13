/**
 * Convert cryptic filenames + state/agency metadata into human-friendly labels.
 *
 * Examples:
 *   540-X-22.pdf + AL/medical → "Alabama Medical Board, Chapter 540-X-22"
 *   §189.3.pdf + TX/medical   → "Texas Medical Board, Rule §189.3"
 *   00000050c.pdf + MS        → "Mississippi Regulation 00000050c"
 */

const STATE_NAMES: Record<string, string> = {
  MS: 'Mississippi',
  AL: 'Alabama',
  AR: 'Arkansas',
  GA: 'Georgia',
  LA: 'Louisiana',
  TN: 'Tennessee',
  TX: 'Texas',
};

const AGENCY_NAMES: Record<string, Record<string, string>> = {
  MS: {
    medical: 'State Board of Medical Licensure',
    dental: 'State Board of Dental Examiners',
    real_estate: 'Real Estate Commission',
  },
  AL: {
    medical: 'Board of Medical Examiners',
    dental: 'Board of Dental Examiners',
    real_estate: 'Real Estate Commission',
  },
  AR: {
    medical: 'State Medical Board',
    dental: 'State Board of Dental Examiners',
    real_estate: 'Real Estate Commission',
  },
  GA: {
    medical: 'Composite Medical Board',
    dental: 'Board of Dentistry',
    real_estate: 'Real Estate Commission',
  },
  LA: {
    medical: 'State Board of Medical Examiners',
    dental: 'State Board of Dentistry',
    real_estate: 'Real Estate Commission',
  },
  TN: {
    medical: 'Board of Medical Examiners',
    dental: 'Board of Dentistry',
    real_estate: 'Real Estate Commission',
  },
  TX: {
    medical: 'Medical Board',
    dental: 'State Board of Dental Examiners',
    real_estate: 'Real Estate Commission',
  },
};

/**
 * Strip the .pdf extension and format the rule/chapter identifier.
 */
function prettyRuleId(filename: string): string {
  const base = filename.replace(/\.pdf$/i, '');

  // Section symbol pattern: §189.3 → Rule §189.3
  if (base.startsWith('§')) return `Rule ${base}`;

  // XX-X-YY or XXX-X pattern: 540-X-22 → Chapter 540-X-22
  if (/^\d{2,4}-[A-Z]-\d+$/i.test(base)) return `Chapter ${base}`;

  // Dotted rule: 46v33 → Title 46 v33
  const tv = base.match(/^(\d+)v(\d+)$/);
  if (tv) return `Title ${tv[1]}, Vol. ${tv[2]}`;

  // Numeric like 038.00.04-002F-7509: Rule 038.00.04
  if (/^\d{3}\.\d{2}/.test(base)) return `Rule ${base}`;

  // MS Phase 1 opaque IDs: 00000050c → Regulation 00000050c
  if (/^\d{8}[a-z]?$/i.test(base)) return `Regulation ${base}`;

  // Dotted number: 0460-01.20230919 → Chapter 0460-01
  if (/^\d{4}-/.test(base)) return `Chapter ${base}`;

  return base;
}

/**
 * Build a human-friendly citation label from document + metadata.
 */
export function formatCitationLabel(
  filename: string,
  state?: string,
  agencyType?: string,
): string {
  const ruleId = prettyRuleId(filename);

  const stateName = state ? STATE_NAMES[state.toUpperCase()] : '';
  const agencyName = state && agencyType
    ? AGENCY_NAMES[state.toUpperCase()]?.[agencyType.toLowerCase()]
    : '';

  if (stateName && agencyName) {
    return `${stateName} ${agencyName} — ${ruleId}`;
  }
  if (stateName) {
    return `${stateName} ${ruleId}`;
  }
  return ruleId;
}

/**
 * A shorter version for compact pill display.
 */
export function formatCitationShort(
  filename: string,
  state?: string,
  agencyType?: string,
): string {
  const ruleId = prettyRuleId(filename);

  if (state && agencyType) {
    const agencyShort = {
      medical: 'Med.',
      dental: 'Dent.',
      real_estate: 'RE',
    }[agencyType.toLowerCase()] || agencyType;
    return `${state}/${agencyShort} — ${ruleId}`;
  }
  if (state) {
    return `${state} — ${ruleId}`;
  }
  return ruleId;
}
