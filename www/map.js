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
var SITE_TIME_OFFSET = -3

//------------------ Init functions ------------------------------------------//

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: {lat: -33.114974, lng: -68.481041},
        zoom: 18
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);

    // set date
    $( "#datepicker" ).datepicker();
    $( "#datepicker" ).datepicker('setDate', 'today');

    // set time
    defaultDate = new Date();
    $('#timepicker').timepicker({
        showNowButton: true,
        showDeselectButton: true,
        showCloseButton: true,
    });
    $('#timepicker').timepicker('setTime', defaultDate.toLocaleTimeString(
                                'es-AR', { hour: "numeric",
                                minute: "numeric"}));
    load_data();
}

function load_data(loop){
    clearLinks();

    // set default time to current time minux 5 mins
    var date        = $("#datepicker").datepicker('getDate');
    var time        = $("#timepicker").timepicker('getTime').split(':');
    var localOffset = new Date().getTimezoneOffset()/60;
    date.setHours(parseInt(time[0]) - localOffset, time[1]);
    isoTime = date.toISOString();

    // MOTE CREATE
    var solType     = "SOL_TYPE_DUST_EVENTMOTECREATE";
    var encType     = encodeURIComponent(solType);
    var encTime     = encodeURIComponent(isoTime);
    $.getJSON("api/v1/jsonp/ARG_junin/" + encType + "/time/" + encTime, create_motes);

    // LINKS CREATE
    solType         = "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS";
    encType         = encodeURIComponent(solType);
    $.getJSON("api/v1/jsonp/ARG_junin/" + encType + "/time/" + encTime, create_links);

    if (loop != 0)
        timeout = setTimeout(load_data, 30000);
    else
        clearTimeout(timeout)
}

//------------------ Main functions ------------------------------------------//

// populate the motes list
function create_motes(data){
    for (var i=0; i < data.length; i++) {
        // populate table
        motes[data[i].value.moteId] = {
            "mac"       : data[i].value.macAddress,
            "marker"    : null
        }
    }
}

function create_links(data){

    // update motes location
    for (var i=0; i < data.length; i++) {
        udpateMoteLocation(
            data[i].mac,
            data[i].value.latitude,
            data[i].value.longitude);
    }

    // create links
    for (var i=0; i < data.length; i++) {
        for (var j=0; j<data[i].value.neighbors.length; j++){
            var neighbor = data[i].value.neighbors[j];
            if (neighbor.neighborId in motes){
                var crd1 = getLocationFromMac(data[i].mac);
                var crd2 = getLocationFromId(neighbor.neighborId)
                if (crd1 != null && crd2 != null){
                    var lineCoords = [crd1, crd2];
                    var link    = getLink(crd1, crd2);

                    // get metric
                    var pdr     = ((neighbor.numTxPackets- neighbor.numTxFailures)
                                    /neighbor.numTxPackets
                                  ) * 100;
                    var rssi    = neighbor.rssi;

                    // set line parameters
                    var content =   "RSSI: " + rssi + "dBm<br>" +
                                    "PDR: " + pdr + "%"
                    var color   = getLinkColor(rssi, pdr);

                    // update link if already exists and new rssi is worst
                    if (link != null){
                        if (neighbor.rssi < link.metric.rssi){
                            link.pline.setMap(null);
                            link.pline          = createPolyline(lineCoords, content, color);
                            link.metric.rssi    = rssi;
                            link.metric.pdr     = pdr;
                        }
                    } // create link if it does not already exists
                    else {
                        var l = createPolyline(lineCoords, content, color);
                        newLink = {
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
        if (pdr >= GOOD_LINK_PDR)
            return GOOD_LINK_COLOR;
        else if (pdr > MEDIUM_LINK_COLOR && pdr < GOOD_LINK_COLOR)
            return MEDIUM_LINK_COLOR;
        else if (pdr < 0)
            return BAD_LINK_COLOR;
        else
            return UNKNOWN_LINK_COLOR;
    }
}

function udpateMoteLocation(mac, lat, lng){
    var moteId = null;
    for (var i=0; i<motes.length; i++) {
        if (i in motes){
            if (motes[i].mac == mac){
                if (motes[i].marker == null){
                    motes[i].marker = createMarker(lat, lng, mac);
                } else if (motes[i].marker.position.lat() != lat ||
                            motes[i].marker.position.lng() != lng) {
                    motes[i].marker.setMap(null);
                    motes[i].marker = createMarker(lat, lng, mac);
                }
            }
        }
    }
}

function createMarker(lat, lng, content){
    // create Markers
    var myLatLng = new google.maps.LatLng(lat, lng)
    var marker = new google.maps.Marker({
        position: myLatLng,
        map: map,
    });
    // add popup listener
    infoBox(map, marker, content);
    return marker;
}

function createPolyline(lineCoordinates, content, color){
    var opacity = 1.0;
    if (color == UNKNOWN_LINK_COLOR)
      opacity = 0.0001;
    var line = new google.maps.Polyline({
          path: lineCoordinates,
          geodesic: true,
          strokeColor: color,
          strokeOpacity: opacity,
          strokeWeight: 2
    });
    line.setMap(map);
    infoBox(map, line, content);
    return line;
}

function getLink(LatLng1, LatLng2){
    for (i=0; i<links.length; i++) {
        link = links[i].pline;
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
    return null;
    console.log("MAC not found:" + mac)
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
    });
}
