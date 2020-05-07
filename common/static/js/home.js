
$(document).ready( function() {
    let token = $("#oauth2Token").text();
    let mast_uri = $("#mastodonURI").text();
    let id = $("#userMastodonID").text();

    let userInfoSpinner = $("#spinner").clone().removeAttr("hidden");
    let followersSpinner = $("#spinner").clone().removeAttr("hidden");
    let followingSpinner = $("#spinner").clone().removeAttr("hidden");
    $("#userInfoCard").append(userInfoSpinner);
    $("#userRelationCard h5:first").append(followingSpinner);
    $("#userRelationCard h5:last").append(followersSpinner);
    $(".mast-following-more").hide();
    $(".mast-followers-more").hide();

    getUserInfo(
        id, 
        mast_uri, 
        token, 
        function(userData) {
            let userName;
            if (userData.display_name) {
                userName = translateEmojis(userData.display_name, userData.emojis);
            } else {
                userName = userData.username;
            }
            $(".mast-user .mast-avatar").attr("src", userData.avatar);
            $(".mast-user .mast-displayname").html(userName);
            $(".mast-user .mast-brief").text($(userData.note).text());
            $(userInfoSpinner).remove();
        }
    );

    getFollowers(
        id,
        mast_uri,
        token,
        function(userList, request) {
            if (userList.length == 0) {
                $(".mast-followers").hide();
            } else {
                if (userList.length > 4){
                    userList = userList.slice(0, 4);
                    $(".mast-followers-more").show();
                }
                let template = $(".mast-followers li").clone();
                $(".mast-followers").html("");
                userList.forEach(data => {
                    temp = $(template).clone();
                    temp.find("img").attr("src", data.avatar);
                    if (data.display_name) {
                        temp.find("a").html(translateEmojis(data.display_name, data.emojis));
                    } else {
                        temp.find("a").text(data.username);
                    }
                    let url = $("#userPageURL").text().replace('0', data.id);
                    temp.find("a").attr('href', url);
                    $(".mast-followers").append(temp);
                });
            }
            $(followersSpinner).remove();
        }
    );

    getFollowing(
        id,
        mast_uri,
        token,
        function(userList, request) {
            if (userList.length == 0) {
                $(".mast-following").hide();
            } else {
                if (userList.length > 4){
                    userList = userList.slice(0, 4);
                    $(".mast-following-more").show();
                }
                let template = $(".mast-following li").clone();
                $(".mast-following").html("");
                userList.forEach(data => {
                    temp = $(template).clone()
                    temp.find("img").attr("src", data.avatar);
                    if (data.display_name) {
                        temp.find("a").html(translateEmojis(data.display_name, data.emojis));
                    } else {
                        temp.find("a").text(data.username);
                    }
                    let url = $("#userPageURL").text().replace('0', data.id);
                    temp.find("a").attr('href', url);
                    $(".mast-following").append(temp);
                });
            }
            $(followingSpinner).remove();

        }
    );

});