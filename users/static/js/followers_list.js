
$(document).ready( function() {
    let token = $("#oauth2Token").text();
    let mast_uri = $("#mastodonURI").text();
    let id = $("#userMastodonID").text();
    let nextUrl = null;
    let requesting = false;

    let userInfoSpinner = $("#spinner").clone().removeAttr("hidden");
    let followersSpinner = $("#spinner").clone().removeAttr("hidden");
    let followingSpinner = $("#spinner").clone().removeAttr("hidden");
    let mainSpinner = $("#spinner").clone().removeAttr("hidden");

    $("#main .user:first").hide();

    $("#main").append(mainSpinner);
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
            let subUserList = null;
            if (userList.length == 0) {
                $(".mast-followers").hide();
            } else {
                if (userList.length > 4){
                    subUserList = userList.slice(0, 4);
                    $(".mast-followers-more").show();
                }
                let template = $(".mast-followers li").clone();
                $(".mast-followers").html("");
                subUserList.forEach(data => {
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
            // main
            let template = $("#main .user").clone().show();

            userList.forEach(data => {
                temp = $(template).clone();
                temp.find(".avatar").attr("src", data.avatar);
                if (data.display_name) {
                    temp.find(".user-name").html(translateEmojis(data.display_name, data.emojis));
                } else {
                    temp.find(".user-name").text(data.username);
                }
                let url = $("#userPageURL").text().replace('0', data.id);
                temp.find("a").attr('href', url);
                temp.find(".user-brief").text(data.note.replace(/(<([^>]+)>)/ig,""));
                $("#main .user:last").after(temp);                
            });

            mainSpinner.hide();
            request.getResponseHeader('link').split(',').forEach(link => {
                if (link.includes('next')) {
                    let regex = /<(.*?)>/;
                    nextUrl = link.match(regex)[1];
                }
            });            
        }
    );

    getFollowing(
        id,
        mast_uri,
        token,
        function(userList, request) {
            // aside
            if (userList.length == 0) {
                $("#aside .mast-following").hide();
            } else {
                if (userList.length > 4){
                    userList = userList.slice(0, 4);
                    $("#aside .mast-following-more").show();
                }
                let template = $("#aside .mast-following li").clone();
                $("#aside .mast-following").html("");
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
                    $("#aside .mast-following").append(temp);
                });
            }
            $(followingSpinner).remove();
        }
    );

        
    $(window).scroll(function() {
        let scrollPosition = $(window).scrollTop();
        // test if scoll to bottom 
        if (scrollPosition + 0.5> $(document).height()-$(window).height()) {
            if (!requesting && nextUrl) {
                // acquire lock
                requesting = true;
                mainSpinner.show();
                $.ajax({
                    url: nextUrl,
                    method: 'GET',
                    data: {
                        'limit': NUMBER_PER_REQUEST,
                    },
                    headers: {
                        'Authorization': 'Bearer ' + token,
                    },
                    success: function(userList, status, request){
                        if(userList.length == 0 ) {
                            mainSpinner.hide();
                            return;
                        }
                        let template = $("#main .user:first").clone().show();
                        let newUrlFlag = false;
                        request.getResponseHeader('link').split(',').forEach(link => {
                            if (link.includes('next')) {
                                let regex = /<(.*?)>/;
                                nextUrl = link.match(regex)[1];
                                newUrlFlag = true;
                            }
                        });
                        if (!newUrlFlag) {
                            nextUrl = null;
                        }
                        userList.forEach(data => {
                            temp = $(template).clone()
                            temp.find(".avatar").attr("src", data.avatar);
                            if (data.display_name) {
                                temp.find(".user-name").html(translateEmojis(data.display_name, data.emojis));
                            } else {
                                temp.find(".user-name").text(data.username);
                            }
                            let url = $("#userPageURL").text().replace('0', data.id);
                            temp.find("a").attr('href', url);
                            temp.find(".user-brief").text($(data.note).text());
                            $("#main .user:last").after(temp);                
                        });                            
                        mainSpinner.hide();
                        // release lock   
                        // console.log(userList[userList.length-1].username)
                        // console.log(nextUrl)    
                        requesting = false;
                    },
                });        
            }
        }
    });


});
