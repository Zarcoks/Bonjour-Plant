/* The live players of the video page: one HLS reader per <video data-hls>.
   Started after every HTMX swap, since picking a camera replaces the player,
   and stopped as soon as its <video> has left the page — a reader nobody
   watches would go on pulling the feed off the Raspberry Pi. */
(function () {
  // How many times a player tries to come back from a fatal trouble before the
  // frame says the feed is not arriving.
  var RECOVERIES = 3;

  var readers = [];

  // The readers whose player is gone are the ones nothing shows any more.
  function stopTheOnesLeft() {
    readers = readers.filter(function (reader) {
      if (document.body.contains(reader.player)) {
        return true;
      }
      reader.hls.destroy();
      return false;
    });
  }

  // A feed that never came says so in the frame, in place of a black rectangle.
  // The message is looked for beside the player rather than under a named
  // frame: the same player is framed by the video page on one page and by the
  // opened card of a plant on the other, and a frame that is not the one named
  // would take the picture away without putting anything in its place.
  function unavailable(player) {
    var frame = player.parentNode;
    var message = frame && frame.querySelector('.video-unavailable');
    if (message) {
      message.hidden = false;
    }
    player.remove();
  }

  function start(player) {
    var stream = player.dataset.hls;
    if (!stream || player.dataset.playing) {
      return;
    }
    player.dataset.playing = 'yes';

    // Safari reads HLS on its own, and does it better than any library would.
    if (player.canPlayType('application/vnd.apple.mpegurl')) {
      player.addEventListener('error', function () { unavailable(player); });
      player.src = stream;
      return;
    }

    if (!window.Hls || !window.Hls.isSupported()) {
      unavailable(player);
      return;
    }

    var hls = new window.Hls({ liveDurationInfinity: true });
    var recoveries = 0;

    hls.on(window.Hls.Events.ERROR, function (event, trouble) {
      // Everything else is hls.js recovering on its own, which it does well:
      // only what it gives up on is dealt with here.
      if (!trouble.fatal) {
        return;
      }
      // A live feed is worth insisting on: a camera reboots, a network blinks,
      // MediaMTX republishes a path. Giving up on the first fatal error would
      // leave a black frame where the picture was about to come back.
      if (recoveries < RECOVERIES) {
        recoveries += 1;
        if (trouble.type === window.Hls.ErrorTypes.NETWORK_ERROR) {
          hls.startLoad();
          return;
        }
        if (trouble.type === window.Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError();
          return;
        }
      }
      hls.destroy();
      unavailable(player);
    });

    // A feed that came back is a feed that may break again, later, on its own
    // terms: what was spent recovering from the last trouble is given back.
    hls.on(window.Hls.Events.FRAG_BUFFERED, function () { recoveries = 0; });
    hls.loadSource(stream);
    hls.attachMedia(player);
    readers.push({ player: player, hls: hls });
  }

  function play() {
    stopTheOnesLeft();
    Array.prototype.forEach.call(document.querySelectorAll('video[data-hls]'), start);
  }

  play();
  document.body.addEventListener('htmx:afterSwap', play);
})();
