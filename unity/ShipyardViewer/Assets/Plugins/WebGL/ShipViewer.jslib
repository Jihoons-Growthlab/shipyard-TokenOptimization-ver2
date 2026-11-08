mergeInto(LibraryManager.library, {
  ShipViewer_NotifyReady: function () {
    Module.canvas.dispatchEvent(new CustomEvent('shipviewer-ready'));
  },
});
