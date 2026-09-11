function lesion_result = detectLesions(net, image)
% DETECTLESIONS Runs U-Net lesion segmentation for Microaneurysms and Exudates.
%
% Inputs:
%   net   - Imported segmentation dlnetwork/DAGNetwork (or empty for fallback)
%   image - Input image matrix (HxWx3 uint8) or file path string
%
% Outputs:
%   lesion_result - Struct with fields:
%                     .ma_mask    - Logical binary mask for microaneurysms
%                     .ex_mask    - Logical binary mask for exudates
%                     .ma_present - Boolean true if microaneurysms detected
%                     .ex_present - Boolean true if exudates detected

    if ischar(image) || isstring(image)
        image = imread(char(image));
    end

    [origH, origW, ~] = size(image);

    % Segmentation ONNX model expects 512x512 image
    targetSize = [512, 512];
    imgResized = imresize(image, targetSize);
    
    ma_mask = false(origH, origW);
    ex_mask = false(origH, origW);

    if ~isempty(net)
        try
            % Normalize image to single [0, 1] or uint8 depending on import
            inputTensor = single(imgResized) / 255.0;
            
            % Predict 2-channel output logits/probabilities [512, 512, 2]
            output = predict(net, inputTensor);
            
            % Extract channels: 1 -> Microaneurysms, 2 -> Exudates
            if ndims(output) == 4 % [1, 2, 512, 512] or [1, 512, 512, 2]
                if size(output, 2) == 2
                    ma_map = squeeze(output(1, 1, :, :));
                    ex_map = squeeze(output(1, 2, :, :));
                else
                    ma_map = squeeze(output(1, :, :, 1));
                    ex_map = squeeze(output(1, :, :, 2));
                end
            elseif ndims(output) == 3 % [512, 512, 2]
                ma_map = output(:, :, 1);
                ex_map = output(:, :, 2);
            else
                ma_map = double(output > 0.5);
                ex_map = double(output > 0.5);
            end

            % Apply Sigmoid if raw logits are returned
            if max(ma_map(:)) > 1.0 || min(ma_map(:)) < 0.0
                ma_map = 1.0 ./ (1.0 + exp(-ma_map));
                ex_map = 1.0 ./ (1.0 + exp(-ex_map));
            end

            % Threshold to binary mask
            ma_mask_512 = ma_map > 0.35;
            ex_mask_512 = ex_map > 0.35;

            % Morphological cleaning to eliminate small noise spots (< 5 pixels)
            ma_mask_512 = bwareaopen(ma_mask_512, 5);
            ex_mask_512 = bwareaopen(ex_mask_512, 5);

            % Resize masks back to original image dimensions
            ma_mask = imresize(ma_mask_512, [origH, origW], 'nearest');
            ex_mask = imresize(ex_mask_512, [origH, origW], 'nearest');
        catch me
            warning('detectLesions:InferenceFailed', 'Segmentation model inference failed: %s. Using heuristic detection.', me.message);
            [ma_mask, ex_mask] = heuristicLesionDetection(image);
        end
    else
        % Fallback heuristic detector when network is not loaded
        [ma_mask, ex_mask] = heuristicLesionDetection(image);
    end

    ma_present = any(ma_mask(:));
    ex_present = any(ex_mask(:));

    lesion_result = struct(...
        'ma_mask', ma_mask, ...
        'ex_mask', ex_mask, ...
        'ma_present', ma_present, ...
        'ex_present', ex_present ...
    );
end

function [ma_mask, ex_mask] = heuristicLesionDetection(image)
    % Classical CV heuristic for Microaneurysms (dark spots) and Exudates (bright spots)
    [H, W, ~] = size(image);
    greenChan = double(image(:, :, 2));
    
    % CLAHE enhancement on green channel
    G_norm = adapthisteq(uint8(greenChan), 'ClipLimit', 0.02);
    G_norm = double(G_norm);

    % Exudates: bright yellowish/white lesions on green channel
    ex_raw = G_norm > 210;
    ex_mask = bwareaopen(ex_raw, 10);

    % Microaneurysms: tiny dark reddish focal spots
    % Top-hat filtering to highlight dark structures
    se = strel('disk', 4);
    topHat = imclose(G_norm, se) - G_norm;
    ma_raw = topHat > 30 & G_norm < 120;
    ma_mask = bwareaopen(ma_raw, 3);
end
