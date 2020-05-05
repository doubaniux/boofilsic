$(document).ready( function() {
    
    
    $(".modal-close").on('click', function() {
        $(this).parents(".modal").hide();
        $(".bg-mask").hide();
    });

    $("#aside .mark .button-group .button").each(function() {
        $(this).click(function(e) {
            e.preventDefault();
            let title = $(this).text().trim();
            $(".mark-modal .modal-title").text(title);
            $(".mark-modal .modal-body textarea").val("");
            let status = $(this).data('status')
            $("input[name='status'][value='"+status+"']").prop("checked", true)
            $(".bg-mask").show();
            $(".mark-modal").show();

            // if wish, hide rating widget in modal
            if ($(this).attr("id") == "wishButton") {
                console.log($(this).attr("id"))
                $(".mark-modal .rating-star-edit").hide();
            } else {
                $(".mark-modal .rating-star-edit").show();
            }

        });
    })

    $(".mark a.edit").click(function(e) {
        e.preventDefault();
        let title = $(".mark-status-label").text().trim();
        $(".mark-modal .modal-title").text(title);
        $(".bg-mask").show();
        $(".mark-modal").show();
    });

    // readonly star rating of detail display section
    let ratingLabels = $("#main .rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
        });
    });
    // readonly star rating at aside section
    ratingLabels = $("#aside .rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
            starSize: 15,
        });
    });

    // editable rating star in modal
    ratingLabels = $("#modals .rating-star-edit");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $("input[type='hidden'][name='rating']").val() / 2;
        let label = $(this);
        label.starRating({
            initialRating: ratingScore,
            starSize: 20,
            onHover: function(currentIndex, currentRating, $el){
                $("input[type='hidden'][name='rating']").val(currentIndex);
            },
            onLeave: function(currentIndex, currentRating, $el){
                $("input[type='hidden'][name='rating']").val(currentRating * 2);
            }            
        });
    });
    
    // hide rating star when select wish
    const WISH_CODE = 1;
    if ($(".modal-selection input[type='radio']:checked").val() == WISH_CODE) {
        $(".mark-modal .rating-star-edit").hide();
    }
    $(".modal-selection input[type='radio']").click(function() {
        // 2 is the status code of wish
        if ($(this).val() == WISH_CODE) {
            $(".mark-modal .rating-star-edit").hide();
        } else {
            $(".mark-modal .rating-star-edit").show();
        }
        
    });

    // show confirm modal
    $(".mark form a").click(function(e) {
        e.preventDefault();
        $(".modal.confirm-modal").show();
        $(".bg-mask").show();
    });

    // confirm modal
    $(".confirm-modal input[type='submit']").click(function(e) {
        e.preventDefault();
        $(".mark form").submit();
    });
    
});