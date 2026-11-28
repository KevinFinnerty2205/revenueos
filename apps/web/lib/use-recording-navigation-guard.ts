import { useLayoutEffect } from "react";

const unfinishedRecordingNotice =
  "Finish recording and uploading, or cancel the recording in Notes & capture before leaving this page.";

export function useRecordingNavigationGuard(blocked: boolean) {
  useLayoutEffect(() => {
    if (!blocked) return;

    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    function protectWorkspaceLink(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        !(event.target instanceof Element)
      ) {
        return;
      }

      const link = event.target.closest<HTMLAnchorElement>("a[href]");
      if (!link || link.hasAttribute("download")) return;
      if (link.target && link.target.toLowerCase() !== "_self") return;

      const { origin, pathname, search } = window.location;
      if (
        link.origin !== origin ||
        (link.pathname === pathname && link.search === search)
      ) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      window.alert(unfinishedRecordingNotice);
    }

    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("click", protectWorkspaceLink, true);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      document.removeEventListener("click", protectWorkspaceLink, true);
    };
  }, [blocked]);
}
