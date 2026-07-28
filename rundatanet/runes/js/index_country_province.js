export const SWEDISH_AREA_CODES = new Set([
  'Öl', 'Ög', 'Sö', 'Sm', 'Vg', 'U', 'Vs', 'Nä', 'Vr', 'Gs',
  'Hs', 'M', 'Ån', 'D', 'Hr', 'J', 'Lp', 'Ds', 'Bo', 'G', 'SE'
]);

export const COUNTRY_OR_PROVINCE_OPTIONS = [
  { text: 'Sweden, whole', value: 'all_sweden' },
  { text: 'Öland (Öl)', value: 'Öl ' }, { text: 'Östergötland (Ög)', value: 'Ög ' }, { text: 'Södermanland (Sö)', value: 'Sö ' },
  { text: 'Småland (Sm)', value: 'Sm ' }, { text: 'Västergötland (Vg)', value: 'Vg ' }, { text: 'Uppland (U)', value: 'U ' },
  { text: 'Västmanland (Vs)', value: 'Vs ' }, { text: 'Närke (Nä)', value: 'Nä ' }, { text: 'Värmland (Vr)', value: 'Vr ' },
  { text: 'Gästrikland (Gs)', value: 'Gs ' }, { text: 'Hälsingland (Hs)', value: 'Hs ' }, { text: 'Medelpad (M)', value: 'M ' },
  { text: 'Ångermanland (Ån)', value: 'Ån ' }, { text: 'Dalarna (D)', value: 'D ' }, { text: 'Härjedalen (Hr)', value: 'Hr ' },
  { text: 'Jämtland (J)', value: 'J ' }, { text: 'Lappland (Lp)', value: 'Lp ' }, { text: 'Dalsland (Ds)', value: 'Ds ' },
  { text: 'Bohuslän (Bo)', value: 'Bo ' }, { text: 'Gotland (G)', value: 'G ' }, { text: 'Sweden, other (SE)', value: 'SE ' },
  { text: 'Denmark (DR)', value: 'DR ' }, { text: 'Norway (N)', value: 'N ' }, { text: 'Faroe Islands (FR)', value: 'FR ' },
  { text: 'Greenland (GR)', value: 'GR ' }, { text: 'Iceland (IS)', value: 'IS ' }, { text: 'Finland (FI)', value: 'FI ' },
  { text: 'Shetland (Sh)', value: 'Sh ' }, { text: 'Orkney (Or)', value: 'Or ' }, { text: 'Scotland (Sc)', value: 'Sc ' },
  { text: 'England (E)', value: 'E ' }, { text: 'Isle of Man (IM)', value: 'IM ' }, { text: 'Ireland (IR)', value: 'IR ' },
  { text: 'France (F)', value: 'F ' }, { text: 'Netherlands (NL)', value: 'NL ' }, { text: 'Germany (DE)', value: 'DE ' },
  { text: 'Poland (PL)', value: 'PL ' }, { text: 'Latvia (LV)', value: 'LV ' }, { text: 'Russia (RU)', value: 'RU ' },
  { text: 'Ukraine (UA)', value: 'UA ' }, { text: 'Byzantium (By)', value: 'By ' }, { text: 'Italy (IT)', value: 'IT ' },
  { text: 'Other areas (X)', value: 'X ' },
];

function normalizeCountryProvinceText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[()[\],.]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitCountryProvinceValues(value) {
  if (Array.isArray(value)) {
    return value.flatMap(splitCountryProvinceValues);
  }

  return String(value || '')
    .replace(/Sweden\s*,\s*whole/gi, 'Sweden whole')
    .split(/[|,\n]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

function optionMatchKeys(option) {
  const textWithoutCode = option.text.replace(/\s*\([^)]*\)\s*/g, '').trim();
  const textBeforeComma = textWithoutCode.split(',')[0].trim();
  return [
    option.value.trim(),
    option.text,
    textWithoutCode,
    textBeforeComma,
  ].map(normalizeCountryProvinceText).filter(Boolean);
}

function resolveCountryProvinceToken(token) {
  const normalizedToken = normalizeCountryProvinceText(token);
  if (!normalizedToken) {
    return [];
  }

  const matches = COUNTRY_OR_PROVINCE_OPTIONS.filter(option => {
    return optionMatchKeys(option).some(key => key === normalizedToken);
  });

  if (matches.length > 0) {
    return matches.map(option => option.value);
  }

  return [String(token || '').trim()];
}

export function resolveCountryProvinceValues(value) {
  const values = splitCountryProvinceValues(value).flatMap(resolveCountryProvinceToken);
  const uniqueValues = [];
  const seen = new Set();

  values.forEach(value => {
    const key = String(value || '').trim();
    if (!key || seen.has(key)) {
      return;
    }
    seen.add(key);
    uniqueValues.push(value);
  });

  return uniqueValues;
}

export function formatCountryProvinceRuleValue(value) {
  const values = Array.isArray(value) ? value : splitCountryProvinceValues(value);
  return values.map(item => {
    const normalizedItem = normalizeCountryProvinceText(item);
    const option = COUNTRY_OR_PROVINCE_OPTIONS.find(option => {
      return optionMatchKeys(option).some(key => key === normalizedItem);
    });
    return option ? option.text : String(item || '').trim();
  }).filter(Boolean).join(', ');
}

export function getCountryProvinceSuggestions(value) {
  const term = String(value || '');
  const match = term.match(/^(.*[|,\n])([^|,\n]*)$/s);
  const prefix = match ? match[1] : '';
  const query = normalizeCountryProvinceText(match ? match[2] : term);
  const normalizedPrefix = prefix ? prefix.replace(/\s*$/, '') + ' ' : '';

  return COUNTRY_OR_PROVINCE_OPTIONS
    .map((option, index) => {
      const keys = optionMatchKeys(option);
      let rank = 0;
      if (query) {
        if (keys.some(key => key === query)) {
          rank = 1;
        } else if (keys.some(key => key.startsWith(query))) {
          rank = 2;
        } else if (keys.some(key => key.includes(query))) {
          rank = 3;
        } else {
          rank = 99;
        }
      }
      return { option, index, rank };
    })
    .filter(item => item.rank < 99)
    .sort((left, right) => left.rank - right.rank || left.index - right.index)
    .map(item => item.option)
    .map(option => normalizedPrefix + option.text);
}
