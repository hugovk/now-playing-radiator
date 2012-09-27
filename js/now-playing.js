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
            $('body').css("background-image", "");
            $('#artwork').css("background-image", "");
            $("#favicon").remove();
            $('<link id="favicon" rel="shortcut icon" href="images/favicon.ico" />').appendTo('head');
        }
        else if (track.artist != this.lastArtist && track.name != this.lastTitle) {

            // Check artwork
            if (track.artwork && track.artwork.length &&
                track.artwork != this.lastArtwork) {
                $('#artwork').css("background-image", "url('" + track.artwork + "')");
                this.lastArtwork = track.artwork;
            }
            else {
                $('#artwork').css("background-image", "");
            }
            
            // Check favicon
            if (track.favicon && track.favicon.length &&
                track.favicon != this.lastFavicon) {
                $("#favicon").remove();
                $('<link id="favicon" rel="shortcut icon" href="' + track.favicon + '" />').appendTo('head');
                this.lastFavicon = track.favicon;
                }
            else {
                $("#favicon").remove();
                $('<link id="favicon" rel="shortcut icon" href="images/favicon.ico" />').appendTo('head');
            }
            
            // sneaky image one-liner borrowed from TwitSpace™
            var image = "http://ws.audioscrobbler.com/2.0/?method=artist.getimageredirect&artist=" + encodeURI(track.artist) + "&api_key=b25b959554ed76058ac220b7b2e0a026&size=original";
            $('body').css("background-image", "url('" + image + "')");
        }
        if (track.artist != ' ') {
            $('#artist').html('<span class="separator">by </span> <a target="linky" href="http://last.fm/music/' + encodeURI(track.artist) + '">' + track.artist + '</a>');
            document.title = track.artist + " - " + track.name;
            }
        else {
            $('#artist').html('<span class="separator">[silence]</span>');
            document.title = "Now Playing";
            }
        $('#track').html('<a target="linky" href="' + track.url + '">' + track.name + '</a>');
        if (track.artist && track.name)
            $('#lyrics').html('<a target="linky" href="http://lyrics.wikia.com/' + encodeURI(track.artist) + ':' + encodeURI(track.name) + '">Lyrics</a>');
        else
            $('#lyrics').html('');
        if (track.album)
            $('#album').html('| Album: <a target="linky" href="http://last.fm/music/' + encodeURI(track.artist) + '/' + encodeURI(track.album) + '">' + track.album + '</a>');
        else
            $('#album').html('');
        if (track.artist != ' ') {
            this.lastArtist = track.artist;
            this.lastTitle  = track.name;
        }
        this.updateHeader(track);
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
        }
        else {
            this.display({artist: ' ', name: ''});
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