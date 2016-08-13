// LINK LIMITS
var GOOD_LINK_RSSI      = -70;
var MEDIUM_LINK_RSSI    = -80;
var GOOD_LINK_PDR       = 80;
var MEDIUM_LINK_PDR     = 50;

// LINK COLOR
var GOOD_LINK_COLOR     = "#00ff00"     // green
var MEDIUM_LINK_COLOR   = "#ffff00"     // orange
var BAD_LINK_COLOR      = "#ffff00"     // red
var UNKNOWN_LINK_COLOR  = "#ffffff"     // white

// Global variables
var map;
var motes   = [];         // a list of motes, indexed by id
var links   = [];         // a list of links
var timeout;
var infoWindow;
var SITE_TIME_OFFSET    = -3
var DEFAULT_PDR         = 101 // init to impossible value
var board_colors        = {"#c33c1c":null,"#dbd60d":null,"#acd2cd":null,"#ff9966":null}


//------------------ Init functions ------------------------------------------//

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: new google.maps.LatLng(0, 0),
        zoom: 18,
        scaleControl: true,
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);

    // set date
    $( "#datepicker" ).datepicker();
    $( "#datepicker" ).datepicker('setDate', 'today');

    // set time
    defaultDate = new Date();
    defaultDate.setTime(defaultDate.getTime());
    $('#timepicker').timepicker({
        showNowButton: true,
        showDeselectButton: true,
        showCloseButton: true,
    });
    $('#timepicker').timepicker('setTime', defaultDate.toLocaleTimeString(
                                'es-AR', { hour: "numeric",
                                minute: "numeric"}));
    load_data(1);
}

function load_data(loop){
    clearLinks();

    // set default time to current time minux 5 mins
    var date        = $("#datepicker").datepicker('getDate');
    var time        = $("#timepicker").timepicker('getTime').split(':');
    var localOffset = new Date().getTimezoneOffset()/60;
    date.setHours(parseInt(time[0]) - localOffset, time[1]);
    isoTime = date.toISOString();

    // get host and site name
    var host        = window.location.origin
    var sitename    = $("#sitename").val()
    var path        = window.location.pathname.split("/map")[0]

    // MOTE CREATE
    var solType     = "SOL_TYPE_DUST_SNAPSHOT";
    var encType     = encodeURIComponent(solType);
    var encTime     = encodeURIComponent(isoTime);
    $.getJSON(host+ path +
        "/api/v1/jsonp/"+sitename+"/" + encType +
        "/time/" + encTime, create_motes);

    // LINKS CREATE
    solType         = "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS";
    encType         = encodeURIComponent(solType);
    $.getJSON(host+ path +
        "/api/v1/jsonp/"+sitename+"/" + encType +
        "/time/" + encTime, create_links);

    if (loop == 1)
        timeout = setTimeout(load_data, 30000);
    else
        clearTimeout(timeout)
}

//------------------ Main functions ------------------------------------------//

// populate the motes list
function create_motes(data){
    if (Object.keys(data).length > 0) {

        mote_list = data[0].value.mote
        for (var i=0; i < Object.keys(mote_list).length; i++) {
            // populate table
            motes[mote_list[i].moteId] = {
                "mac"       : mote_list[i].macAddress,
                "marker"    : null
            }
        }
    }
}

function create_links(data){
    var bounds = new google.maps.LatLngBounds();
    var loc;

    // update motes location and board type
    for (var i=0; i < data.length; i++) {
        loc = new google.maps.LatLng(
            data[i].value.latitude,
            data[i].value.longitude
        );
        bounds.extend(loc);
        udpateMote(
            data[i].mac,
            data[i].value.latitude,
            data[i].value.longitude,
            data[i].value.board);
    }
    map.fitBounds(bounds);
    map.panToBounds(bounds);

    // create links
    for (var i=0; i < data.length; i++) {
        for (var n_id in data[i].value.neighbors){
            var neighbor = data[i].value.neighbors[n_id]
            if (neighbor.neighborId in motes){
                var crd1 = getLocationFromMac(data[i].mac);
                var crd2 = getLocationFromId(neighbor.neighborId)
                if (crd1 != null && crd2 != null){
                    var lineCoords = [crd1, crd2];
                    var link    = getLink(crd1, crd2);

                    // get metric
                    var pdr = DEFAULT_PDR //init to unpossible value
                    if (neighbor.numTxPackets > 0){
                        pdr     = ((neighbor.numTxPackets - neighbor.numTxFailures)
                                    /neighbor.numTxPackets
                                ) * 100;
                    }
                    var rssi    = neighbor.rssi;


                    // update link if already exists
                    if (link != null){
                        link.metric.rssi    = Math.min(rssi, link.metric.rssi)
                        link.metric.pdr     = Math.min(pdr, link.metric.pdr)

                        link.pline.setMap(null);
                        var color   = getLinkColor(link.metric.rssi, link.metric.pdr);
                        var dist    = calcDistance(lineCoords[0],lineCoords[1])
                        // set line parameters
                        if (link.metric.pdr == DEFAULT_PDR)
                          s_pdr = "No Tx"
                        else
                          s_pdr = link.metric.pdr + "%"
                        var content =   "RSSI: " + rssi + "dBm<br>" +
                                        "PDR: " + s_pdr + "<br>" +
                                        "Distance: " + dist + "m"
                        link.pline  = createPolyline(lineCoords, content, color);
                    } // create link if it does not already exists
                    else {
                        var color   = getLinkColor(rssi, pdr);
                        var dist    = calcDistance(lineCoords[0],lineCoords[1])
                        // set line parameters
                        // set line parameters
                        if (pdr == DEFAULT_PDR)
                          s_pdr = "No Tx"
                        else
                          s_pdr = pdr + "%"
                        var content =   "RSSI: " + rssi + "dBm<br>" +
                                        "PDR: " + s_pdr + "<br>" +
                                        "Distance: " + dist + "m"
                        var l = createPolyline(lineCoords, content, color);
                        var newLink = {
                            "pline" :   l,
                            "metric":   {
                                    "rssi"  : rssi,
                                    "pdr"   : pdr,
                                }
                        }
                        links.push(newLink);
                    }
                }
            }
            else {console.log("ID not found:" + neighbor.neighborId);}
        }
    }
}

//----------------Interface Listeners ---------------------------------------//

$(document).ready(function() {
    $("#next_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // add 5 minutes
        var newDate = new Date(selectedTime.getTime() + 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        load_data(0);
    });
});

$(document).ready(function() {
    $("#prev_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // remove 5 minutes
        var newDate = new Date(selectedTime.getTime() - 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        load_data(0)
    });
});

//------------------ Helpers ------------------------------------------------//

function clearLinks(){
    // remove links
    for (var i=0; i<links.length; i++) {
        if (i in links){
            links[i].pline.setMap(null);
        }
    }
    links = [];
    links.length = 0;
}

function getLinkColor(rssi, pdr){
    var metric = $("#metric").val()

    if (metric == "rssi"){
        if (rssi > GOOD_LINK_RSSI)
            return GOOD_LINK_COLOR;
        else if (rssi >= MEDIUM_LINK_RSSI && rssi <= GOOD_LINK_RSSI)
            return MEDIUM_LINK_COLOR;
        else
            return BAD_LINK_COLOR;
    }
    else if (metric == "pdr"){
        if (pdr == DEFAULT_PDR)
            return UNKNOWN_LINK_COLOR;
        if (pdr >= GOOD_LINK_PDR)
            return GOOD_LINK_COLOR;
        else if (pdr > MEDIUM_LINK_PDR && pdr < GOOD_LINK_PDR)
            return MEDIUM_LINK_COLOR;
    }
}

function getMoteColor(board){
    if (board == null)
        board = "unknown"
    for (var color in board_colors){
        if (board_colors[color] === null){
            board_colors[color] = board;
            return color;
        }
        else if (board_colors[color] === board){
            return color
        }
    }
    // return default color if board_color is too small
    return "#FFF"
}

function udpateMote(mac, lat, lng, board){
    var moteId  = null;
    var color   = getMoteColor(board)
    for (var i=0; i<motes.length; i++) {
        if (i in motes){
            if (motes[i].mac == mac){
                var content = mac + "<br>"
                if (board != null)
                  content += board + "<br>"
                if (motes[i].marker == null){
                    motes[i].marker = createMarker(lat, lng, content, color);
                } else if (motes[i].marker.position.lat() != lat ||
                            motes[i].marker.position.lng() != lng) {
                    motes[i].marker.setMap(null);
                    motes[i].marker = createMarker(lat, lng, content, color);
                }
            }
        }
    }
}

function createMarker(lat, lng, content, color){
    // create Markers
    var myLatLng = new google.maps.LatLng(lat, lng)
    var marker = new google.maps.Marker({
        position: myLatLng,
        map: map,
        icon: pinSymbol(color),
    });
    // add popup listener
    infoBox(map, marker, content);
    return marker;
}

function createPolyline(lineCoordinates, content, color){
    var line = new google.maps.Polyline({
          path: lineCoordinates,
          geodesic: true,
          strokeColor: color,
          strokeWeight: 2
    });
    if (color != UNKNOWN_LINK_COLOR){
        line.setMap(map);
        infoBox(map, line, content);
    }
    return line;
}

function getLink(LatLng1, LatLng2){
    for (i=0; i<links.length; i++) {
        var link = links[i].pline;
        var coord1 = "("+link.getPath().getAt(0).lat()+", "+link.getPath().getAt(0).lng()+")"
        var coord2 = "("+link.getPath().getAt(1).lat()+", "+link.getPath().getAt(1).lng()+")"
        if ( ((LatLng1.toString() == coord1) && (LatLng2.toString() == coord2)) ||
             ((LatLng2.toString() == coord1) && (LatLng1.toString() == coord2))
           ){
            return links[i]
        }
    }
    return null
}

function getMoteFromId(moteId){
    if (motes[moteId].marker != null)
        return motes[moteId].marker.position;
    else
        return null;
}

function getLocationFromId(moteId){
    if (motes[moteId].marker != null)
        return motes[moteId].marker.position;
    else
        return null;
}

function getLocationFromMac(mac){
    for( i=0; i<motes.length; i++ ) {
        if (i in motes && motes[i].mac == mac){
            return motes[i].marker.position;
        }
    }
    console.log("MAC not found:" + mac)
    return null;
}

// calculates distance between two points in meters
function calcDistance(p1, p2) {
    return (google.maps.geometry.spherical.computeDistanceBetween(p1, p2)).toFixed(2);
}

/*Function that shows a window with the content or info
 about the marker (sensor location)*/

function infoBox(map, marker, content) {
    infoWindow = new google.maps.InfoWindow();
    // Attaching a click event to the current marker
    google.maps.event.addListener(marker, "click", function(e) {
        infoWindow.setPosition(e.latLng);
        infoWindow.setContent(content);
        infoWindow.open(map, marker);
        var iw_container = $(".gm-style-iw").parent();
        iw_container.stop().hide();
        iw_container.fadeIn(300);
    });
}

// Function that create a vectorial image of a marker with the given color
function pinSymbol(color) {
    return {
        path: 'M 0,0 C -2,-20 -10,-22 -10,-30 A 10,10 0 1,1 10,-30 C 10,-22 2,-20 0,0 z M -2,-30 a 2,2 0 1,1 4,0 2,2 0 1,1 -4,0',
        fillColor: color,
        fillOpacity: 1,
        strokeColor: '#000',
        strokeWeight: 2,
        scale: 1,
   };
}
