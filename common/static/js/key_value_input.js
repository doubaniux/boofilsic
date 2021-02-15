function keyValueInput(valueKeyWidget, hiddenInput) {
    let placeholderKey = valueKeyWidget.attr('placeholder-key');
    let placeholderValue = valueKeyWidget.attr('placeholder-value');
    if (placeholderKey == null) {
        placeholderKey = '';
    }
    
    if (placeholderValue == null) {
        placeholderValue = '';
    }
    // assign existing pairs to hidden input
    setHiddenInput(valueKeyWidget);

    let newInputPair = $('<input type="text"' + 'placeholder=' + placeholderKey + '><input type="text"' + 'placeholder=' + placeholderValue + '>');
    valueKeyWidget.append(newInputPair.clone());
    // add new input pair
    valueKeyWidget.on('input', ':nth-last-child(1)', function () {
        if ($(this).val() && $(this).prev().val()) {
            valueKeyWidget.append($(newInputPair).clone());
        }
    });
    valueKeyWidget.on('input', ':nth-last-child(2)', function () {
        if ($(this).val() && $(this).next().val()) {
            valueKeyWidget.append($(newInputPair).clone());
        }
    });
    valueKeyWidget.on('input', ':nth-last-child(4)', function () {
        if (!$(this).val() && !$(this).next().val() && valueKeyWidget.children("input").length > 2) {
            $(this).next().remove();
            $(this).remove();
        }
    }); 

    valueKeyWidget.on('input', ':nth-last-child(3)', function () {
        if (!$(this).val() && !$(this).prev().val() && valueKeyWidget.children("input").length > 2) {
            $(this).prev().remove();
            $(this).remove();
        }
    });

    valueKeyWidget.on('input', function () {
        setHiddenInput(this);
    });

    function setHiddenInput(elem) {
        let keys = $(elem).children(":nth-child(odd)").map(function () {
            if ($(this).val()) {
                return $(this).val();
            }
        }).get();
        let values = $(elem).children(":nth-child(even)").map(function () {
            if ($(this).val()) {
                return $(this).val();
            }
        }).get();
        if (keys.length == values.length) {
            let finalValue = [];
            keys.forEach(function (key, i) {
                let json = new Object;
                json[key] = values[i];
                finalValue.push(JSON.stringify(json))
            });
            hiddenInput.val(finalValue.toString());
        } else if (keys.length - values.length == 1) {
            let finalValue = [];
            keys.forEach(function (key, i) {
                let json = new Object;
                if (i < keys.length - 1) {
                    json[key] = values[i];
                } else {
                    json[key] = ''
                }
                finalValue.push(JSON.stringify(json))
            });
            hiddenInput.val(finalValue.toString());
        }
    }


}

