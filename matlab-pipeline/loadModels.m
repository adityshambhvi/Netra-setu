function models = loadModels(modelDir)
% LOADMODELS Imports ONNX DR grading and lesion segmentation models once.
%
% Syntax:
%   models = loadModels()
%   models = loadModels(modelDir)
%
% Inputs:
%   modelDir - (Optional) Path to folder containing ONNX models.
%              Defaults to project root.
%
% Outputs:
%   models   - Struct with fields:
%                .grading_net - Imported ResNet-18 DR grading DAGNetwork/dlnetwork
%                .seg_net     - Imported U-Net lesion segmentation DAGNetwork/dlnetwork

    if nargin < 1 || isempty(modelDir)
        % Default to project root (two levels up from matlab-pipeline/)
        currentDir = fileparts(mfilename('fullpath'));
        modelDir = fullfile(currentDir, '..');
    end

    gradingPath = fullfile(modelDir, 'retinasense_resnet18_weighted_epoch11.onnx');
    segPath     = fullfile(modelDir, 'lesion_seg_model.onnx');

    if ~isfile(gradingPath)
        error('loadModels:FileNotFound', 'DR grading ONNX model not found: %s', gradingPath);
    end

    if ~isfile(segPath)
        error('loadModels:FileNotFound', 'Lesion segmentation ONNX model not found: %s', segPath);
    end

    fprintf('[MATLAB Engine] Importing DR Grading Model (ResNet-18): %s...\n', gradingPath);
    try
        gradingNet = importNetworkFromONNX(gradingPath);
    catch me1
        warning('importNetworkFromONNX failed for grading model: %s. Attempting importONNXNetwork fallback.', me1.message);
        try
            gradingNet = importONNXNetwork(gradingPath, 'OutputLayerType', 'classification');
        catch me2
            gradingNet = [];
            warning('Failed to load DR grading network: %s', me2.message);
        end
    end

    fprintf('[MATLAB Engine] Importing Lesion Segmentation Model (U-Net): %s...\n', segPath);
    try
        segNet = importNetworkFromONNX(segPath);
    catch me1
        warning('importNetworkFromONNX failed for lesion model: %s. Attempting importONNXNetwork fallback.', me1.message);
        try
            segNet = importONNXNetwork(segPath, 'OutputLayerType', 'regression');
        catch me2
            segNet = [];
            warning('Failed to load lesion segmentation network: %s', me2.message);
        end
    end

    models = struct();
    models.grading_net = gradingNet;
    models.seg_net     = segNet;
    models.loaded      = true;
end
