function dopplr(name) {
    // "we take the MD5 digest of the city’s name, convert it to
    //  hex and take the first 6 characters as a CSS RGB value."
    // http://everwas.com/2009/03/dopplr-city-colors.html
    return "#" + md5(name).substring(0, 6);
}
NowPlaying = function(api, user, interval) {
    this.api = api;
    this.user = user;
    this.lastArtist = '';
    this.lastTitle  = '';
    this.lastArtwork = '';
    this.lastFavicon = '';

    /* AutoUpdate frequency - Last.fm API rate limits at 1/sec */
    this.interval = interval || 5;
};
NowPlaying.prototype = {

    display: function(track)
    {
        if (track.artist == ' ') { // clear images
            $('#track-artwork img').hide();
            $('body').css("background-color", "#999");
            $('body').css("background-image", "");
            $('#artwork').css("background-image", "");
            this.reset_favicon();
        }
        else if (track.artist != this.lastArtist && track.name != this.lastTitle) {

            // Get an artist image from Last.fm
            this.api.getArtistInfo(
                track.artist,
                jQuery.proxy(this.handleResponse, this),
                function(error) { console && console.log(error); }
            );

            // Check artwork
            if (track.artwork && track.artwork.length &&
                track.artwork != this.lastArtwork) {
                this.display_album_image(track.artwork);
            }
            else {
                $('body').css("background-color", dopplr(track.artist));
                $('body').css("background-image", "");
                $('#artwork').css("background-image", "");

                // No album image? Fetch one from Last.fm for this track
                this.api.getTrackInfo(
                    track.artist,
                    track.name,
                    jQuery.proxy(this.handleTrackInfoResponse, this),
                    function(error) { console && console.log(error); }
                );
            }

            // Check favicon
            if (track.favicon && track.favicon.length &&
                track.favicon != this.lastFavicon) {
                this.set_favicon(track.favicon);
                }
            else {
                this.reset_favicon();
            }

            // sneaky image one-liner borrowed from TwitSpace™
            // var image = "https://ws.audioscrobbler.com/2.0/?method=artist.getimageredirect&artist=" + encodeURIComponent(track.artist) + "&api_key=5f134f063744307ee6f126ac2c480fab&size=original";
            // $('body').css("background-image", "url('" + image + "')");
        }
        if (track.artist != ' ') {
            $('#artist').html('<span class="separator" style="color:#009bd5;">by </span> <a target="linky" href="https://last.fm/music/' + encodeURIComponent(track.artist) + '">' + track.artist + '</a>');
            document.title = track.artist + " - " + track.name;
            }
        else {
            $('#artist').html('<span class="separator">[silence]</span>');
            document.title = "Now Playing";
            }
            console.log(track)
        $('#track').html('<a target="linky" href="' + track.url + '">' + track.name + '</a>');
        if (track.artist && track.name)
            $('#lyrics').html('<a target="linky" href="http://lyrics.wikia.com/' + encodeURIComponent(track.artist) + ':' + encodeURIComponent(track.name) + '">Lyrics</a>');
        else
            $('#lyrics').html('');
        if (track.album)
            this.display_album_name(track.artist, track.album);
        else
            $('#album').html('');
        if (track.artist != ' ') {
            this.lastArtist = track.artist;
            this.lastTitle  = track.name;
        }
        this.updateHeader(track);
    },

    display_artist_image: function(image)
    {
        $('body').css("background-image", "url('" + image.image + "')");
        this.lastArtwork = image.image;
    },

    display_album_image: function(imageUrl)
    {
        $('#artwork').css("background-image", "url('" + imageUrl + "')");
        this.lastArtwork = imageUrl;
    },

    display_album_name: function(artist, album)
    {
        $('#album').html('| Album: <a target="linky" href="https://last.fm/music/' + encodeURIComponent(artist) + '/' + encodeURIComponent(album) + '">' + album + '</a>');
    },

    reset_favicon: function()
    {
        $("#favicon").remove();
        $('<link id="favicon" rel="shortcut icon" href="images/favicon.ico" />').appendTo('head');
    },

    set_favicon: function(faviconUrl)
    {
        $("#favicon").remove();
        $('<link id="favicon" rel="shortcut icon" href="' + faviconUrl + '" />').appendTo('head');
        this.lastFavicon = faviconUrl;
    },

    update: function()
    {
        this.api.getNowPlayingTrack(
            this.user,
            jQuery.proxy(this.handleResponse, this),
            function(error) { console && console.log(error); }
        );
    },

    autoUpdate: function()
    {
        // Do an immediate update, don't wait an interval period
        this.update();

        // Try and avoid repainting the screen when the track hasn't changed
        setInterval(jQuery.proxy(this.update, this), this.interval * 1000);
    },

    handleResponse: function(response)
    {
        if (response) {
            if (response.artist) {
                var nowplaying = response['@attr'] && response['@attr'].nowplaying;
                this.display({
                    // The API response can vary depending on the user, so be defensive
                    artist: response.artist['#text'] || response.artist.name,
                    name: response.name,
                    favicon: response.image[0]['#text'] || null,
                    artwork: response.image[3]['#text'] || null,
                    nowplaying: nowplaying,
                    url: response.url,
                    album: response.album['#text'] || null
                });
            } else {
                // This'll be the artist image
                this.display_artist_image({
                    image: response
                });

            }
        }
        else {
            this.display({artist: ' ', name: ''});
        }
    },

    handleTrackInfoResponse: function(album)
    {
        if (album) {
            this.display_album_name(album.artist, album.title);
            if (album.image) {
                this.display_album_image(album.image[3]['#text'] || null);
                this.set_favicon(album.image[0]['#text'] || null);
            }
        }
    },

    updateHeader: function(track)
    {
        if (track.nowplaying)
            var status = 'Now playing';
        else
            var status = 'Last played';
        var head = status + ":";
        $('.header').html(head);
    }
};
