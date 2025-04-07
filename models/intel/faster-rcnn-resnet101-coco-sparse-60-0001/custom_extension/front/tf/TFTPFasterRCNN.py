"""
 Copyright (c) 2018 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import logging as log
import networkx as nx
import numpy as np
from ast import literal_eval

# from openvino.tools.mo.front.tf.Preprocessor import PreprocessorReplacement
from openvino.tools.mo.ops.proposal import ProposalOp
from openvino.tools.mo.ops.DetectionOutput import DetectionOutput
from openvino.tools.mo.ops.parameter import Parameter
from openvino.tools.mo.front.common.partial_infer.utils import mark_input_bins, assign_dims_to_weights, int64_array
from openvino.tools.mo.front.common.weights import swap_weights_xy
from openvino.tools.mo.front.extractor import update_attrs, update_ie_fields
from openvino.tools.mo.front.subgraph_matcher import SubgraphMatch
from openvino.tools.mo.front.tf.replacement import FrontReplacementFromConfigFileSubGraph
from openvino.tools.mo.graph.graph import insert_node_after, Node
from openvino.tools.mo.ops.const import Const
from openvino.tools.mo.ops.concat import Concat
from openvino.tools.mo.ops.eltwise import Eltwise
# from openvino.tools.mo.ops.output import Output
from openvino.tools.mo.ops.op import Op
from openvino.tools.mo.ops.permute import Permute
from openvino.tools.mo.ops.reshape import Reshape
from openvino.tools.mo.ops.crop import Crop
from openvino.tools.mo.ops.roipooling import ROIPooling
# from openvino.tools.mo.ops.psroipooling import PSROIPoolingOp
from openvino.tools.mo.ops.interp import InterpOp
# from openvino.tools.mo.ops.roipooling import ROIPooling
# from openvino.tools.mo.ops.softmax import Softmax
from openvino.tools.mo.utils.graph import backward_bfs_for_operation, scope_output_nodes
from openvino.tools.mo.ops.result import Result
from openvino.tools.mo.utils.error import Error
from openvino.tools.mo.utils.pipeline_config import PipelineConfig
from openvino.tools.mo.front.tf.graph_utils import create_op_node_with_second_input


def _value_or_raise(match: SubgraphMatch, pipeline_config: PipelineConfig, key: str):
    """
    Returns value from the 'custom_attributes' of the 'match' object or pipeline_config associated with a key 'key'.
    If the value doesn't exist then raise error.
    :param match: SubgraphMatch object containing 'custom_attributes'.
    :param pipeline_config: PipelineConfig object with parsed values.
    :param key: key to search for.
    :return: the requested value.
    """
    if match and key in match.custom_replacement_desc.custom_attributes:
        return match.custom_replacement_desc.custom_attributes[key]
    value = pipeline_config.get_param(key)
    if value is None:
        raise Error('The sub-graph replacer "[REPLACEMENT_ID]" was not able to find the value for key "{}" in the '
                    'pipeline configuration file specified with the --tensorflow_object_detection_api_pipeline_config '
                    'command line parameter. Update the sub-graph replacement configuration file specified with the '
                    '--transformations_config command line parameter by adding key "{}" with required '
                    'value to the "custom_attributes" dictionary of the "[REPLACEMENT_ID]" replacer.'.format(key, key))
    return value


class TFTPFasterRCNNProposal(FrontReplacementFromConfigFileSubGraph):
    """
    """
    replacement_id = 'TFTPFasterRCNNProposal'

    # def run_after(self):
    #     return [TFTPUpsampling]
    #
    # def run_before(self):
    #     return [TFTPFasterRCNNPSROIPooling]

    def output_edges_match(self, graph: nx.DiGraph, match: SubgraphMatch, new_sub_graph: dict):
        return {match.output_node(0)[0].id: new_sub_graph['proposal_node'].id}

    def nodes_to_remove(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        new_list = match.matched_nodes_names().copy()
        # softmax node
        new_list.append(match.single_input_node(0)[0].in_node(1).id)
        # const node
        new_list.append(match.single_input_node(1)[0].in_node(0).id)
        return new_list

    def generate_sub_graph(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        log.debug('TFTPFasterRCNNProposal: matched_nodes = {}'.format(match.matched_nodes_names()))

        config_attrs = match.custom_replacement_desc.custom_attributes
        nms_threshold = config_attrs['nms_threshold']
        # input_height = graph.graph['preprocessed_image_height']
        # input_width = graph.graph['preprocessed_image_width']
        feat_stride = config_attrs['feat_stride']
        max_proposals = config_attrs['max_proposals']
        anchor_base_size = config_attrs['anchor_base_size']
        # roi_spatial_scale = config_attrs['roi_spatial_scale']
        proposal_ratios = config_attrs['anchor_aspect_ratios']
        proposal_scales = config_attrs['anchor_scales']
        anchors_count = len(proposal_ratios) * len(proposal_scales)

        input_op_with_image_size = Parameter(graph, dict(shape=int64_array([1, 3]), fixed_batch=True))
        input_with_image_size_node = input_op_with_image_size.create_node([], dict(name='image_info'))

        softmax_node = match.single_input_node(1)[0].in_node(1)
        bbox_node = match.single_input_node(0)[0].in_node(0)

        proposal_op = ProposalOp(graph, dict(min_size=12,
                                             framework='',
                                             post_nms_topn=max_proposals,
                                             feat_stride=feat_stride,
                                             ratio=proposal_ratios,
                                             scale=proposal_scales,
                                             base_size=anchor_base_size,
                                             pre_nms_topn=6000,
                                             normalize=1,
                                             nms_thresh=nms_threshold))
                                             # box_coordinate_scale=10, # (0.1, 0.1, 0.2, 0.2)
                                             # box_size_scale=5,
        proposal_node = proposal_op.create_node([softmax_node,
                                                 bbox_node,
                                                 input_with_image_size_node],
                                                dict(name='rcnn_proposal'))
                                                 # match.single_input_node(2)[0].in_node(0)],

        proposal_node['name'] = 'proposals'
        return {'proposal_node': proposal_node}


class TFTPFasterRCNNROIPooling(FrontReplacementFromConfigFileSubGraph):
    """
    This class replaces PSROI pooling sub graph.
    """
    replacement_id = 'TFTPFasterRCNNROIPooling'

    def run_after(self):
        return [TFTPFasterRCNNProposal, TFTPFasterRCNNDetectionOutput]

    def output_edges_match(self, graph: nx.DiGraph, match: SubgraphMatch, new_sub_graph: dict):
        return {match.output_node(0)[0].id: new_sub_graph['roi_pooling_node'].id}

    def nodes_to_remove(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        new_list = match.matched_nodes_names().copy()
        # do not remove nodes that produce box predictions and class predictions
        # new_list.append(match.input_nodes(0)[0][0].id)
        # new_list.remove(match.single_input_node(1)[0].id)
        return new_list

    def generate_sub_graph(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        log.debug('TFTPFasterRCNNROIPooling: matched_nodes = {}'.format(
                  match.matched_nodes_names()))

        config_attrs = match.custom_replacement_desc.custom_attributes
        roi_spatial_scale = config_attrs['spatial_scale']
        pooled_h = config_attrs['pooled_h']
        pooled_w = config_attrs['pooled_w']
        method = config_attrs['method']

        # import ipdb
        # ipdb.set_trace()
        roi_pooling_op = ROIPooling(graph, dict(spatial_scale=roi_spatial_scale,
                                                pooled_h=pooled_h,
                                                pooled_w=pooled_w,
                                                method=method))
        roi_pooling_node = roi_pooling_op.create_node([match.single_input_node(0)[0].in_node(0),
                                                       match.single_input_node(1)[0].in_node(0)],
                                                      dict(name='roi_pooling'))
        return {'roi_pooling_node': roi_pooling_node}


class TFTPFasterRCNNDetectionOutput(FrontReplacementFromConfigFileSubGraph):
    '''
    Replace final outputs to a DetectionOutput layer.
    '''
    replacement_id = 'TFTPFasterRCNNDetectionOutput'

    def run_after(self):
        return [TFTPFasterRCNNProposal]

    def output_edges_match(self, graph: nx.DiGraph, match: SubgraphMatch, new_sub_graph: dict):
        return {match.output_node(0)[0].id: new_sub_graph['detection_output_node'].id}

    def nodes_to_remove(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        new_list = match.matched_nodes_names().copy()
        # do not remove nodes that produce box predictions and class predictions
        # new_list.append(match.input_nodes(0)[0][0].id)
        new_list.remove(match.single_input_node(1)[0].id)
        return new_list

    def generate_sub_graph(self, graph: nx.MultiDiGraph, match: SubgraphMatch):
        log.debug('TFTPFasterRCNNDetectionOutput: matched_nodes = {}'.format(
                  match.matched_nodes_names()))

        config_attrs = match.custom_replacement_desc.custom_attributes

        ops_all = graph.get_op_nodes()
        proposal_node = None
        for o in ops_all:
            try:
                if o.in_node().name == 'proposals':
                    proposal_node = o.in_node()
                    break
            except:
                continue

        cls_score_node = match.single_input_node(1)[0] #.in_node(0)
        bbox_pred_node = match.single_input_node(0)[0].in_node(0)

        reshape_cls_score_node = create_op_node_with_second_input(graph, Reshape,
                                                                  int64_array([1, -1]),
                                                                  dict(name='reshape_cls_score'),
                                                                  cls_score_node)
        reshape_bbox_pred_node = create_op_node_with_second_input(graph, Reshape,
                                                                  int64_array([1, -1]),
                                                                  dict(name='reshape_bbox_pred'),
                                                                  bbox_pred_node)
        crop_op = Crop(graph, dict(axis=int64_array([1]), offset=int64_array([1]), dim=int64_array([4])))
        crop_node = crop_op.create_node([proposal_node], dict(name='crop_proposals'))
        reshape_proposal_node = create_op_node_with_second_input(graph, Reshape,
                                                                 int64_array([1, 1, -1]),
                                                                 dict(name='reshape_proposal'),
                                                                 crop_node)

        pipeline_config = match.custom_replacement_desc.custom_attributes
        num_classes = _value_or_raise(match, pipeline_config, 'num_classes')
        num_proposals = _value_or_raise(match, pipeline_config, 'num_proposals')

        detection_output_op = DetectionOutput(graph, {})
        for key in ('clip_before_nms', 'clip_after_nms'):
            if key in match.custom_replacement_desc.custom_attributes:
                detection_output_op.attrs[key] = int(match.custom_replacement_desc.custom_attributes[key])

        detection_output_node = detection_output_op.create_node(
            [reshape_bbox_pred_node, reshape_cls_score_node, reshape_proposal_node],
            dict(name=detection_output_op.attrs['type'], share_location=0, variance_encoded_in_target=1,
                 num_classes=num_classes,
                 background_label_id=0,
                 normalized=1,
                 code_type='caffe.PriorBoxParameter.CENTER_SIZE', pad_mode='caffe.ResizeParameter.CONSTANT',
                 resize_mode='caffe.ResizeParameter.WARP',
                 confidence_threshold=_value_or_raise(match, pipeline_config, 'score_threshold'),
                 top_k=_value_or_raise(match, pipeline_config, 'topk_per_class'),
                 keep_top_k=_value_or_raise(match, pipeline_config, 'topk_total'),
                 nms_threshold=_value_or_raise(match, pipeline_config, 'nms_threshold')))
        # sets specific name to the node so we can find it in other replacers
        detection_output_node.name = 'detection_output'

        output_op = Result(graph, dict(name='detection_output_node'))
        output_op.create_node([detection_output_node])

        print('The graph output nodes "cls_score", "bbox_pred", "proposals" '
              'have been replaced with a single layer of type "Detection Output". Refer to IR catalogue in the '
              'documentation for information about this layer.')

        return {'detection_output_node': detection_output_node}

