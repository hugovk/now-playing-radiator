/*
 * A simple wrapper to basic Last.fm API functionality
 *
 * Only supports GET and unauthenticated methods, which is 90% of what you
 * need usually, reliant on jquery.
 *
 * @todo add a error callback, catch and handle lfm errors
 *
 */
LastfmAPI = function(api_key) {
    this.api_key = api_key;
};
LastfmAPI.prototype = {
    root: 'https://ws.audioscrobbler.com/2.0/',

    get: function (method, params, success, error)
    {
        jQuery.ajax({
            url: this.root,
            dataType: "jsonp",
            data: jQuery.extend({
                'api_key': this.api_key,
                'format': 'json',
                'method': method
            }, params),
            // Forces JSONP errors to fire, needs re-evaluation if long polling is used
            timeout: 2000
        })
        .success(function(response) {
            (response.error ? error : success)(response);
        })
        .error(function() {
            // JSONP limitations mean we'll only get timeout errors
            console.log({error: 0, message: 'HTTP Error'});
        });
    },

    getNowPlayingTrack: function(user, success, error)
    {
        this.get('user.getrecenttracks', {user: user, limit: '2'}, function(response) {
            var track = response.recenttracks.track[0];

            var fifteenMinsAgo = (+new Date() / 1000) - 900; // unix timestamp for now, minus 15 mins
            if (track && (track.nowplaying || !track.date || track.date.uts >= fifteenMinsAgo)) {
                success(track);
            }
            else {
                success(false);
            }
        }, error);
    },

    getArtistInfo: function(artist, success, error)
    {
        this.get('artist.getinfo', {artist: artist}, function(response) {
            var image = response.artist.image[4]["#text"];
            if (image) {
                success(image);
            }
        }, error);
    },

    getTrackInfo: function(artist, track, success, error)
    {
        this.get('track.getinfo', {artist: artist, track: track}, function(response) {
            if (response.track.album) {
                success(response.track.album);
            }
        }, error);
    }

};
