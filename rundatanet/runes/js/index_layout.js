export const COMPACT_DB_LAYOUT_MEDIA_QUERY =
  '(max-width: 767.98px), (max-width: 1366px) and (any-pointer: coarse)';

const TABLET_MAX_WIDTH = 1366;

function getViewportWidth(windowObject) {
  const documentWidth = windowObject.document
    && windowObject.document.documentElement
    ? windowObject.document.documentElement.clientWidth
    : 0;
  return Math.max(documentWidth || 0, windowObject.innerWidth || 0);
}

function isTouchTabletFallback(windowObject, navigatorObject) {
  const viewportWidth = getViewportWidth(windowObject);
  if (!viewportWidth || viewportWidth > TABLET_MAX_WIDTH) {
    return false;
  }

  const userAgent = String(navigatorObject.userAgent || '');
  const platform = String(navigatorObject.platform || '');
  const hasTouch = Number(navigatorObject.maxTouchPoints || 0) > 0
    || 'ontouchstart' in windowObject;
  const isIPadOS = /iPad/i.test(userAgent)
    || (platform === 'MacIntel' && Number(navigatorObject.maxTouchPoints || 0) > 1);
  const isAndroidTablet = /Android|Silk|Kindle/i.test(userAgent);

  return hasTouch && (isIPadOS || isAndroidTablet);
}

export function isCompactDbLayout(
  windowObject = typeof window !== 'undefined' ? window : null,
  navigatorObject = typeof navigator !== 'undefined' ? navigator : {}
) {
  if (!windowObject) {
    return false;
  }

  try {
    if (typeof windowObject.matchMedia === 'function'
      && windowObject.matchMedia(COMPACT_DB_LAYOUT_MEDIA_QUERY).matches) {
      return true;
    }
    return isTouchTabletFallback(windowObject, navigatorObject);
  } catch (error) {
    return false;
  }
}

export function syncCompactDbLayoutClass() {
  if (typeof document === 'undefined' || !document.documentElement) {
    return false;
  }
  const compact = isCompactDbLayout();
  document.documentElement.classList.toggle('db-compact-layout', compact);
  return compact;
}

export function initCompactDbLayout() {
  const compact = syncCompactDbLayoutClass();
  if (typeof window === 'undefined' || typeof window.addEventListener !== 'function') {
    return compact;
  }

  window.addEventListener('resize', syncCompactDbLayoutClass);
  window.addEventListener('orientationchange', syncCompactDbLayoutClass);
  return compact;
}
