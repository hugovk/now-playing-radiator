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
            timeout: 2000,
            success: function(response) {
                (response.error ? error : success)(response);
            },
            error: function() {
                // JSONP limitations mean we'll only get timeout errors
                console.log({error: 0, message: 'HTTP Error'});
            },
        })
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
            const mbid = response.artist.mbid;
            console.table(response);
            if (mbid) {
               const url = 'https://musicbrainz.org/ws/2/artist/' + mbid + '?inc=url-rels&fmt=json';
               console.log(url);
                fetch(url)
                    .then(res => res.json())
                    .then((out) => {
                        const relations = out.relations;
                        console.table(relations);
                        // Find image relation
                        for (let i = 0; i < relations.length; i++) {
                            if (relations[i].type === 'image') {
                                let image_url = relations[i].url.resource;
                                if (image_url.startsWith('https://commons.wikimedia.org/wiki/File:')) {
                                    const filename = image_url.substring(image_url.lastIndexOf('/') + 1);
                                    image_url = 'https://commons.wikimedia.org/wiki/Special:Redirect/file/' + filename;
                                }
                                console.log(image_url);
                                success(image_url);
                            }
                        }
                    })
                    .catch(err => { throw console.log(err) });
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
