import { useEffect } from 'react'

/**
 * While active, asks for confirmation before a reload, window close or in-app link click would
 * discard unsaved edits. BrowserRouter has no navigation blocker, so link clicks are intercepted
 * in the capture phase before React Router handles them.
 */
export function useUnsavedChangesGuard(active: boolean, message: string): void {
  useEffect(() => {
    if (!active) return

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault()
      event.returnValue = ''
    }

    function handleClick(event: MouseEvent) {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const anchor = event.target instanceof Element ? event.target.closest('a[href]') : null
      if (!anchor || anchor.hasAttribute('download') || anchor.getAttribute('target') === '_blank') return
      if (!window.confirm(message)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    document.addEventListener('click', handleClick, true)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      document.removeEventListener('click', handleClick, true)
    }
  }, [active, message])
}
