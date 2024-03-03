# Author- Carl Bass
# Date - 2024-02-17
# Description- Fusion add-in that maps a surfaces parametric (u,v) space to (x,y) coordinates

import adsk.core, adsk.fusion, adsk.cam, traceback
import os

# Global list to keep all event handlers in scope.
handlers = []

# global variables available in all functions
app = adsk.core.Application.get()
ui  = app.userInterface

# global variables because I can't find a better way to pass this info around -- would be nice if fusion api had some cleaner way to do this
debug = False
chordal_deviation = 0.1
scale_factor = 1.

def run(context):
    try:
        global tool_diameter

        # Find where the python file lives and look for the icons in the ./.resources folder
        python_file_folder = os.path.dirname(os.path.realpath(__file__))
        resource_folder = os.path.join (python_file_folder, 'resources')

        # Get the CommandDefinitions collection so we can add a command
        command_definitions = ui.commandDefinitions

        tooltip = 'Maps lines, arcs and fitted splines from sketch to surface'

        # Create a button command definition.
        uv_xy_button = command_definitions.addButtonDefinition('UV_to_XY', 'UV to XY', tooltip, resource_folder)
        
        # Connect to the command created event.
        uv_xy_command_created = command_created()
        uv_xy_button.commandCreated.add (uv_xy_command_created)
        handlers.append(uv_xy_command_created)

        # add the Moose Tools and the xy to uv button to the Tools tab
        utilities_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if utilities_tab:
            # get or create the "Moose Tools" panel.
            moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
            if not moose_tools_panel:
                moose_tools_panel = utilities_tab.toolbarPanels.add('MoosePanel', 'Moose Tools')

        if moose_tools_panel:
            # Add the command to the panel.
            control = moose_tools_panel.controls.addCommand(uv_xy_button)
            control.isPromoted = False
            control.isPromotedByDefault = False
            debug_print ('Moose Tools installed and control added')
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Event handler for the commandCreated event.
class command_created (adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            inputs = command.commandInputs
    
            # Connect to the execute event.
            on_execute = command_executed()
            command.execute.add(on_execute)
            handlers.append(on_execute)

            # create the face selection input
            face_selection_input = inputs.addSelectionInput('face_select', 'Face', 'Select the face')
            face_selection_input.addSelectionFilter('Faces')
            face_selection_input.setSelectionLimits(1,1)

            inputs.addFloatSpinnerCommandInput ('chordal_deviation', 'Chordal deviation', 'in', 0.1 , 1.0 , .05, chordal_deviation)

            #inputs.addFloatSpinnerCommandInput ('scale_factor', 'Sketch scale factor', '', 0.01 , 100.0 , 1, scale_factor)

            # create debug checkbox
            inputs.addBoolValueInput('debug', 'Debug', True, '', False)
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Event handler for the execute event.
class command_executed (adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        global debug
        global chordal_deviation
        global scale_factor

        try:
            design = app.activeProduct

            # get current command
            command = args.firingEvent.sender

            for input in command.commandInputs:
                if (input.id == 'face_select'):
                    face = input.selection(0).entity
                elif (input.id == 'chordal_deviation'):
                    chordal_deviation = input.value  
                    debug_print (f'chordal deviation = {chordal_deviation:.2f} in or cm? ')     
                #elif (input.id == 'scale_factor'):
                #    scale_factor = input.value    
                elif (input.id == 'debug'):
                    debug = input.value                      
                else:
                    debug_print (f'OOOPS --- too much input')

            root_component = design.rootComponent
            sketches = root_component.sketches

            debug_print (f'------------- face ----------')

            uv_range = face.evaluator.parametricRange()
            u_min = uv_range.minPoint.x
            u_max = uv_range.maxPoint.x            
            v_min = uv_range.minPoint.y
            v_max = uv_range.maxPoint.y
            debug_print (f'u = {u_min:.2f} to {u_max:.2f} {face.evaluator.isClosedInU}')
            debug_print (f'v = {v_min:.2f} to {v_max:.2f} {face.evaluator.isClosedInV}')
            
            u_range = u_max - u_min
            v_range = v_max - v_min
            

            debug_print (f'range of u = {u_range:.2f} v =  {v_range:.2f}')

            face_min = face.boundingBox.minPoint
            face_max = face.boundingBox.maxPoint

            debug_print (f'x = [{face_min.x:.2f}, {face_max.x:.2f}]')
            debug_print (f'y = [{face_min.y:.2f}, {face_max.y:.2f}]')
            debug_print (f'z = [{face_min.z:.2f}, {face_max.z:.2f}]')

            x_range = face_max.x - face_min.x
            y_range = face_max.y - face_min.y

            # Get the evaluator from the input face.
            surface_evaluator = adsk.core.SurfaceEvaluator.cast(face.evaluator)

            face_range_bounding_box = surface_evaluator.parametricRange()
            face_range_min = face_range_bounding_box.minPoint
            face_range_max = face_range_bounding_box.maxPoint
            
            debug_print (f'face u ranges from {face_range_min.x:.3f} to {face_range_max.x:.3f}')
            debug_print (f'face v ranges from {face_range_min.y:.3f} to {face_range_max.y:.3f}')

            face_min_u = face_range_min.x
            face_max_u = face_range_max.y
            face_min_v = face_range_min.x
            face_max_v = face_range_max.y


            face_min_v = face_range_min.y
            face_max_v = face_range_max.y            
            face_min_u = face_range_min.x
            face_max_u = face_range_max.x

            # this code repeats -- needs to be made into function
            # create isocurves in u but need to find range of v
            face_range_v = face_max_v - face_min_v

            parameters = []   
            sampling_parameters = [.1, .5, .9]

            for sp in sampling_parameters:
                value = face_min_v + (face_range_v * sp)
                parameters.append (value)
                debug_print (f'create curve at v {value:.3f}')

            curves = []
            total_length = 0.0
            num_curves = 0
            for p in parameters:

                curve_collection = surface_evaluator.getIsoCurve(p, True)

                if curve_collection.count == 0:
                    debug_print (f'No curves created')
                    average_length = 0.0
                elif curve_collection.count == 1:
                    num_curves = num_curves + 1
                    for curve in curve_collection:
                        if curve.objectType != adsk.core.NurbsCurve3D.classType():
                            curve = curve.asNurbsCurve

                        (status, edge_start_p, edge_end_p) = curve.evaluator.getParameterExtents()

                        (status, length) = curve.evaluator.getLengthAtParameter (edge_start_p, edge_end_p)

                        debug_print (f'length = {length:.2f}')

                        total_length = total_length + length
                else:
                    debug_print (f'ignore disjoint ones')

            average_length = total_length / num_curves

            debug_print (f'avg length = {average_length:.2f}')

            x_range = average_length

            # find v curves length

            # create isocurves in u but need to find range of v
            face_range_u = face_max_u - face_min_u

            parameters = []   
            sampling_parameters = [.1, .5, .9]

            for sp in sampling_parameters:
                value = face_min_u + (face_range_u * sp)
                parameters.append (value)
                debug_print (f'create curve at u {value:.3f}')

            curves = []
            total_length = 0.0
            num_curves = 0
            for p in parameters:

                curve_collection = surface_evaluator.getIsoCurve(p, False)

                if curve_collection.count == 0:
                    debug_print (f'No curves created')
                    average_length = 0.0
                elif curve_collection.count == 1:
                    num_curves = num_curves + 1
                    for curve in curve_collection:
                        if curve.objectType != adsk.core.NurbsCurve3D.classType():
                            curve = curve.asNurbsCurve

                        (status, edge_start_p, edge_end_p) = curve.evaluator.getParameterExtents()

                        (status, length) = curve.evaluator.getLengthAtParameter (edge_start_p, edge_end_p)

                        debug_print (f'length = {length:.2f}')

                        total_length = total_length + length
                else:
                    debug_print (f'ignore disjoint ones')

            average_length = total_length / num_curves

            debug_print (f'avg length = {average_length:.2f}')

            y_range = average_length

            #y_range = 60

            x_scale = x_range /u_range 
            y_scale = y_range / v_range


            debug_print (f'scale factors u = {x_scale:.2f} v =  {y_scale:.2f}')


            output_sketch = sketches.add (root_component.xYConstructionPlane)
            output_sketch.name = f'UV map'
            sketch_points = output_sketch.sketchPoints

            edges = face.edges

            debug_print (f'------------- edges ----------')

            edge_sketch = sketches.add (root_component.xYConstructionPlane)
            edge_sketch.name = f'edges'
            edge_sketch_points = edge_sketch.sketchPoints

            uvp = adsk.core.Point3D.create (0.0, 0.0, 0.0)

            for e in edges:

                # get parameters of start and end of edge
                (status, start_p, end_p) = e.evaluator.getParameterExtents()
                (status, edge_length) = e.evaluator.getLengthAtParameter (start_p, end_p)

                edge_scale = edge_length / abs(end_p - start_p)

                # get 3D points along the curve
                (status, points) = e.evaluator.getStrokes (start_p, end_p, chordal_deviation)


                #for pt in points:
                #    edge_sketch_points.add (pt)

                #(status, params) = e.evaluator.getParametersAtPoints(points)

                # convert the 3D points to face parameters
                (status, face_parameters) = face.evaluator.getParametersAtPoints(points)


                for uv in face_parameters:
                    uvp.x = uv.x * x_scale
                    uvp.y = uv.y * y_scale
                    uvp.z = 0.0
                    sketch_points.add (uvp)
        
            limits = output_sketch.boundingBox

            debug_print (f'limits x = [{limits.minPoint.x},{limits.maxPoint.x}]')
            debug_print (f'limits y = [{limits.minPoint.y},{limits.maxPoint.y}]')
                        
            # calculate size of xy sketch; for some reason, sketch bounding box doesn't include points in the calculation

            min_x = 100000
            max_x = -min_x        
            min_y = 100000
            max_y = -min_y
           
            for p in sketch_points:
                if p.geometry.x < min_x:
                    min_x = p.geometry.x
                if p.geometry.x > max_x:
                    max_x = p.geometry.x
                if p.geometry.y < min_y:
                    min_y = p.geometry.y
                if p.geometry.y > max_y:
                    max_y = p.geometry.y

            debug_print (f'limits x = [{min_x},{max_x}]')
            debug_print (f'limits y = [{min_y},{max_y}]')
        
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	


def debug_print (msg):
    if debug:
        text_palette = ui.palettes.itemById('TextCommands')
        text_palette.writeText (msg)
        
def stop(context):
    try:
        # clean up the UI
        command_definitions = ui.commandDefinitions.itemById('UV_to_XY')
        if command_definitions:
            command_definitions.deleteMe()
        
        # get rid of this button
        moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
        control = moose_tools_panel.controls.itemById('UV_to_XY')
        if control:
            control.deleteMe()

        # and if it's the last button, get rid of the moose panel
        if moose_tools_panel.controls.count == 0:
                    moose_tools_panel.deleteMe()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	


                    #uvp_sketch = output_sketch.modelToSketchSpace (uvp)
                    #sketch_points.add (uvp_sketch)